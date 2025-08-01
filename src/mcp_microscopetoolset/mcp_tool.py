from mcp.server.fastmcp import FastMCP
from local.execute import Execute

from openai import OpenAI
from agentsNormal.database_agent import DatabaseAgent
from agentsNormal.software_agent import SoftwareEngeneeringAgent
from agentsNormal.error_agent import ErrorAgent
from agentsNormal.strategy_agent import StrategyAgent
from agentsNormal.no_coding_agent import NoCodingAgent
from agentsNormal.logger_agent import LoggerAgent
from agentsNormal.classify_user_intent import ClassifyAgent
from pydantic import Field
from local.prepare_code import prepare_code

mcp_server = FastMCP("Toolset")

_db_agent: DatabaseAgent = None
_software_agent: SoftwareEngeneeringAgent = None
_strategy_agent: StrategyAgent = None
_error_agent: ErrorAgent = None
_no_coding_agent: NoCodingAgent = None
_classification_agent: ClassifyAgent = None
_executor: Execute = None
_openai_client: OpenAI = None
_logger_agent: LoggerAgent = None


def initialize_mcp_tool_agents(db_agent, software_agent, strategy_agent, error_agent, no_coding_agent,
                               executor, openai_client, logger_agent, classification_agent):
    """Initializes the agents used by the MCP tools. Call this once at startup."""
    global _db_agent, _software_agent, _strategy_agent, _error_agent, _no_coding_agent, _executor, _openai_client, _logger_agent, _classification_agent
    _db_agent = db_agent
    _software_agent = software_agent
    _strategy_agent = strategy_agent
    _error_agent = error_agent
    _no_coding_agent = no_coding_agent
    _executor = executor
    _openai_client = openai_client
    _logger_agent = logger_agent
    _classification_agent = classification_agent


@mcp_server.tool(
    name="retrieve_db_context",
    description="Retrieve the most relevant information from the vector database."
)
async def retrieve_db_context(user_query: str = Field(description="The user's original query.")):
    """
    Uses the DatabaseAgent to retrieve the context for answering the user's query.
    """
    return _db_agent.look_for_context(user_query)


@mcp_server.tool(
    name="classify_user_intent",
    description="Classifies the user's initial query to determine their intent (e.g., ask for info, propose strategy, no code needed)."
)
async def classify_user_intent(
        data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Call the internal intent classification logic.
    Returns a dictionary with 'intent' and 'message' (if clarification is needed).
    """
    return _classification_agent.classify_user_intent(data_dict)


@mcp_server.tool(
    name="answer_no_coding_query",
    description="Provides a direct answer to a user query that does not require code generation."
)
async def answer_no_coding_query(
        data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """Uses the NoCodingAgent to generate an answer for non-code-related queries."""
    return _no_coding_agent.no_coding_answer(data_dict)


@mcp_server.tool(
    name="generate_strategy",
    description="Generates a strategic plan for solving a user's request, especially for coding tasks."
)
async def generate_strategy(data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Calls the StrategyAgent to generate a strategy.
    Return a json object with 'intent' (strategy/need_information) and 'message'
    """
    return _strategy_agent.generate_strategy(data_dict)


@mcp_server.tool(
    name="revise_strategy",
    description="Revises an existing strategy based on new information or user feedback."
)
async def revise_strategy(data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Calls the StrategyAgent to revise a strategy.
    Return a json object with 'intent' (new_strategy) and 'message'
    """
    return _strategy_agent.revise_strategy(data_dict)


@mcp_server.tool(
    name="generate_code",
    description="Generates Python code based on the current strategy and context."
)
async def generate_code(data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Calls the SoftwareAgent to generate code.
    Return a json object with 'intent' (code) and 'message'
    """
    return _software_agent.generate_code(data_dict)


@mcp_server.tool(
    name="fix_code",
    description="Fixes existing Python code based on error analysis and context."
)
async def fix_code(data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Calls the SoftwareAgent to fix the code.
    Return a json object with 'intent' (code) and 'message' (the fixed code string)
    """
    return _software_agent.fix_code(data_dict)


@mcp_server.tool(
    name="execute_python_code",
    description="Executes a given Python code string and returns its output or any errors."
)
async def execute_python_code(code_string: str = Field(description="The Python code to execute, as a string.")) -> dict:
    """
    Prepares and executes Python code using the Execute agent.
    Returns a dictionary with 'output' (the execution result) and 'error' (if any).
    """
    try:
        prepare_code_to_run = prepare_code(code_string.strip("```"))
        execution_output = _executor.run_code(prepare_code_to_run)
        if "Error" in execution_output:
            return {'status': 'error', 'output': execution_output}
        else:
            return {'status': 'success', 'output': execution_output}
    except Exception as e:
        return {"status": "error", "output": f"Code preparation/execution failed: {e}"}


@mcp_server.tool(
    name="analyze_errors",
    description="Analyzes an error message from code execution to provide insights for fixing the code."
)
async def analyze_errors(data_dict: dict = Field(description="The current context dictionary of the main agent.")):
    """
    Calls the ErrorAgent to analyze an error.
    Returns a json object with 'intent' (error_analysis) and 'message' (the analysis).
    """
    return _error_agent.analyze_error(data_dict)


@mcp_server.tool(
    name="awaiting_user_approval",
    description="Processes a user's 'yes' or 'no' response for a previously asked approval."
)
async def awaiting_user_approval(user_query: str = Field(description="The user's response, typically 'yes' or 'no'.")):
    """
    Determines if the user approved an action.
    Returns a dictionary with 'approved': True/False and a message.
    """
    if user_query.lower() == "yes":
        return {"approved": True, "message": "User approved the action."}
    else:
        return {"approved": False, "message": "User did not approve the action."}


@mcp_server.tool(
    name="save_result",
    description="Create a summary of the conversation between the user and the agentic system after 'is_final_output' is set to True and add it to the specialized database."
)
async def save_result(data_dict: dict = Field(description="The current context dictionary of the main agent."),
                      user_query: str = Field(description="The user's response, typically 'correct' or 'wrong'.")):
    """
    Calls the LoggerAgent to save the output of the Agents into a database.
    Returns a json object with 'intent' (save) and a message.
    """
    # evaluate user's answer
    if user_query == "correct":
        success = True
    else:
        success = False
    # prepare summary of the code
    summary_chat = _logger_agent.prepare_summary(data_dict)
    if summary_chat.intent == "summary":
        data = {"prompt": summary_chat.message, "output": data_dict['code'], "feedback": success, "category": ""}
        # add into the db
        _db_agent.add_log(data)

    return {"intent": 'save', "message": "The previous result was added to the log database."}
