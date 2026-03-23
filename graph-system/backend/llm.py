"""
llm.py - LLM integration using Google Gemini
- Converts natural language → SQL
- Executes SQL against SQLite
- Returns data-backed natural language answers
- Enforces guardrails: only answers dataset-related questions
"""

import os
import json
import re
import google.generativeai as genai
from database import get_schema_info, execute_query
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-1.5-flash")

# ── GUARDRAIL SYSTEM PROMPT ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a data analyst assistant for a business intelligence system.
You ONLY answer questions about the dataset described below.
You must REFUSE any question unrelated to this dataset, including:
- General knowledge questions (history, science, coding, math, etc.)
- Creative writing, storytelling, role-play
- Personal advice or opinions
- Anything not related to orders, deliveries, billing, payments, customers, or products

If the user asks something unrelated, respond ONLY with:
{"guardrail": true, "message": "This system is designed to answer questions related to the provided business dataset only. Please ask about orders, deliveries, billing, customers, or products."}

For valid dataset questions, respond ONLY with valid JSON in this format:
{
  "guardrail": false,
  "sql": "SELECT ...",
  "explanation": "Brief one-line explanation of what the SQL does"
}

Rules for SQL generation:
- Use ONLY the tables and columns that exist in the schema below
- Use table aliases for clarity
- Limit results to 100 rows maximum using LIMIT 100
- For tracing flows, use JOINs across sales_orders, deliveries, billing_documents
- Never use DROP, INSERT, UPDATE, DELETE, or any DML/DDL

DATABASE SCHEMA:
{schema}

IMPORTANT: Return ONLY valid JSON. No markdown. No backticks. No extra text.
"""

ANSWER_PROMPT = """You are a business intelligence assistant. Given a SQL query result, 
write a concise, professional natural language answer to the user's original question.

Rules:
- Be specific and data-driven
- Mention actual numbers, IDs, or values from the data
- Keep it under 150 words
- Do NOT make up data — only use what's in the query results
- If results are empty, say "No records found matching your query."
- Format lists as bullet points when there are multiple items

User Question: {question}
SQL Executed: {sql}
Query Results (JSON): {results}

Write a clear, concise answer:"""


class LLMQueryEngine:
    def __init__(self):
        self._schema_cache = None

    def _get_schema(self):
        if not self._schema_cache:
            self._schema_cache = get_schema_info()
        return self._schema_cache

    def invalidate_cache(self):
        self._schema_cache = None

    def _classify_and_generate_sql(self, question: str, conversation_history: list = None):
        """Step 1: Use Gemini to classify the question and generate SQL."""
        schema = self._get_schema()
        system = SYSTEM_PROMPT.format(schema=schema)

        # Build conversation context
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-4:]:  # Last 4 turns for context
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

        prompt = f"{system}\n\nConversation so far:\n{history_text}\nUser question: {question}"

        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()

            # Strip markdown fences if present
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            raw = raw.strip()

            parsed = json.loads(raw)
            return parsed
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return {"guardrail": True, "message": "Could not parse query. Please rephrase your question about the dataset."}
        except Exception as e:
            return {"guardrail": True, "message": f"LLM error: {str(e)}"}

    def _generate_answer(self, question: str, sql: str, results: list):
        """Step 2: Generate natural language answer from SQL results."""
        results_str = json.dumps(results[:20], indent=2, default=str)  # Limit to 20 for context
        prompt = ANSWER_PROMPT.format(
            question=question,
            sql=sql,
            results=results_str
        )
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Query executed successfully. Found {len(results)} records."

    def query(self, question: str, conversation_history: list = None):
        """
        Main query pipeline:
        1. Classify (is it dataset-related?)
        2. Generate SQL
        3. Execute SQL
        4. Generate NL answer
        Returns structured response dict.
        """
        # Step 1: Classify and generate SQL
        llm_response = self._classify_and_generate_sql(question, conversation_history)

        # Guardrail triggered
        if llm_response.get("guardrail"):
            return {
                "type": "guardrail",
                "message": llm_response.get("message", "This system only answers dataset-related questions."),
                "sql": None,
                "results": [],
                "answer": llm_response.get("message", ""),
                "highlighted_nodes": []
            }

        sql = llm_response.get("sql", "")
        if not sql:
            return {
                "type": "error",
                "message": "Could not generate a valid SQL query.",
                "sql": None,
                "results": [],
                "answer": "I couldn't formulate a query for that question. Please try rephrasing.",
                "highlighted_nodes": []
            }

        # Step 2: Execute SQL
        results, error = execute_query(sql)
        if error:
            return {
                "type": "sql_error",
                "message": error,
                "sql": sql,
                "results": [],
                "answer": f"The generated query had an error: {error}. Please try rephrasing.",
                "highlighted_nodes": []
            }

        # Step 3: Generate NL answer
        answer = self._generate_answer(question, sql, results or [])

        # Step 4: Extract highlighted node IDs from results
        highlighted_nodes = []
        if results:
            id_keys = [k for k in results[0].keys() if "id" in k.lower()]
            for row in results[:10]:
                for key in id_keys:
                    val = row.get(key)
                    if val:
                        # Map to graph node format
                        label_map = {
                            "sales_order_id": "SalesOrder",
                            "customer_id": "Customer",
                            "delivery_id": "Delivery",
                            "billing_id": "Billing",
                            "material_id": "Product",
                            "payment_id": "Payment",
                            "journal_id": "Journal",
                        }
                        label = label_map.get(key, key.replace("_id", "").title())
                        highlighted_nodes.append(f"{label}:{val}")

        return {
            "type": "success",
            "message": llm_response.get("explanation", ""),
            "sql": sql,
            "results": results or [],
            "answer": answer,
            "highlighted_nodes": list(set(highlighted_nodes))
        }


# Singleton
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = LLMQueryEngine()
    return _engine
