from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from server.llm.prompts import buyer_prompt, seller_prompt, resumo_prompt, prompt_interestChecker, first_interest_prompt
from server.models.schemas import AgentResponse
from server.config import OPENAI_API_KEY, OPENAI_MODEL_NAME

# LLMs
openai_llm = ChatOpenAI(
    model_name=OPENAI_MODEL_NAME,
    openai_api_key=OPENAI_API_KEY,
    temperature=0.3
)

# Output parser
parser = PydanticOutputParser(pydantic_object=AgentResponse)

# Cadeias LLM
buyer_chain = buyer_prompt | openai_llm | parser
seller_chain = seller_prompt | openai_llm 
resumo_chain = resumo_prompt | openai_llm
first_interest_chain = first_interest_prompt | openai_llm
interestChecker_chain = prompt_interestChecker | openai_llm