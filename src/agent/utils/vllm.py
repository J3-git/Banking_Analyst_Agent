from pydantic import BaseModel
from openai   import OpenAI

# HELPER — single LLM call with/without LM Format Enforcer
def _call_llm(user_prompt: str,
              model_name: str,
              client : OpenAI,
              model_class: type[BaseModel] | None = None,
              system_prompt: str | None = None,
              max_tokens: int = 200,
              ) -> str:
    
    if not system_prompt:
        system_prompt = """
            You are a Banking Loan Analyst AI.

            Your responsibilities:
            * Answer user queries related to customers, loans, and repayments using available tools and database data.
            * Always prefer tool outputs over assumptions. Do not fabricate data.

            Strict rules:
            1. Never hallucinate. If data is missing or a tool fails, clearly say "Data not available" or return the error.
            2. Only answer using verified tool results or explicitly provided information.
            3. Do not infer or guess customer details, financial values, or statuses.
            4. Respect data privacy:

            * Only return data for the requested customer_id.
            * Do not expose data of other customers.
            5. Follow schema strictly when generating tool inputs (JSON format, correct fields only).
            6. If user intent is unclear, ask a clarification question instead of guessing.
            7. Keep responses concise, factual, and professional.
            8. Do not perform actions outside banking analytics scope.

            Output guidelines:
            * Use structured, clear responses.
            * Summarize insights when appropriate (e.g., risk, overdue behavior).
            * If no results found, explicitly state it.

            You are a reliable data analyst, not a creative assistant.
            """

    kwargs = {}
    if model_class:
        kwargs["extra_body"] = {
            "structured_outputs": {
                "json": model_class.model_json_schema(),
                "_backend": "lm-format-enforcer",
                "disable_fallback": True
            }
        }

    response = client.chat.completions.create(
    model=model_name,
    messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
    max_tokens=max_tokens,         # intent is short
    temperature=0.0,       # deterministic — always pick most likely token
    **kwargs
    )
    return response.choices[0].message.content.strip()