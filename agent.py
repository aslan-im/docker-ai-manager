import os
import json
import yaml
from openai import OpenAI
from tools import RemoteDockerManager
from dotenv import load_dotenv
from pydantic import ValidationError
from tools_schema import (
    DelegateArgs,
    MONITOR_TOOLS,
    ADMIN_TOOLS,
    ORCHESTRATOR_TOOLS
)

from tools_schema import (
    ListContainersArgs,
    GetContainerLogsArgs, 
    RestartContainerArgs, 
    WaitArgs, 
    InspectContainerArgs,
    CheckDiskSpaceArgs
)

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

docker_managers: dict[str, RemoteDockerManager] = {}
for server in config['servers']:
    docker_managers[server['name']] = RemoteDockerManager(
        name=server['name'],
        host=server['host'],
        username=server['username'],
        key_filename=server['key_filename']
    )

AVAILABLE_SERVERS = ", ".join(f"'{name}'" for name in docker_managers)

def load_system_prompt(filepath="system_prompt.txt"):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

SYSTEM_PROMPT = load_system_prompt()


load_dotenv()
API_KEY = os.getenv("API_KEY")
client = OpenAI(api_key=API_KEY)


def _resolve_manager(server_name: str) -> "RemoteDockerManager | str":
    mgr = docker_managers.get(server_name)
    if mgr is None:
        return f"Error: Unknown server '{server_name}'. Available servers: {AVAILABLE_SERVERS}"
    return mgr


def interact_with_agent(messages: list, active_tools: list, model_name: str = "gpt-5.4-mini") -> str:

    """
    Processes the current message history through the ReAct loop 
    until the model provides a final text response.
    Modifies the messages list in-place to preserve conversation context.
    """
    while True:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=active_tools if active_tools else None,
            tool_choice="auto" if active_tools else "none"
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                raw_arguments = tool_call.function.arguments
                
                print(f"\n🛠️  [Agent Action Request]: {function_name} with args {raw_arguments}")
                
                if function_name == "restart_container":
                    print(f"⚠️   CRITICAL: Agent wants to execute a destructive command!")
                    user_approval = input(f"Allow execution of {function_name}? (y/n): ").strip().lower()
                    if user_approval != 'y' and user_approval != 'yes':
                        print("❌ Execution denied by user.")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": "Error: Operation denied by the human administrator. Choose an alternative strategy."
                        })
                        continue
                try:
                    if function_name == "delegate_to_monitor":
                        args = DelegateArgs.model_validate_json(raw_arguments)
                        print(f"\n   ↳ 👔 Orchestrator delegates to Monitor: {args.instruction}")

                        sub_messages = [
                            {
                                "role": "system",
                                "content": "You are a read-only Monitor Agent. Fetch logs, check disk space, and list containers based on instructions. Return a clear summary. IMPORTANT: The ONLY available servers are: {AVAILABLE_SERVERS}."
                            },
                            {
                                "role": "user",
                                "content": args.instruction
                            }
                        ]

                        tool_output = interact_with_agent(sub_messages, MONITOR_TOOLS, model_name="gpt-5.4-mini")
                    elif function_name == "delegate_to_admin":
                        args = DelegateArgs.model_validate_json(raw_arguments)
                        print(f"\n   ↳ 👔 Orchestrator delegates to Admin: {args.instruction}")

                        sub_messages = [
                            {
                                "role": "system",
                                "content": "You are an Admin Agent. Execute restart and wait commands based on instructions. Return a clear summary. IMPORTANT: The ONLY available servers are: {AVAILABLE_SERVERS}."
                            },
                            {
                                "role": "user",
                                "content": args.instruction
                            }
                        ]

                        tool_output = interact_with_agent(sub_messages, ADMIN_TOOLS, model_name="gpt-5.4-mini")
                    
                    elif function_name == "list_containers":
                        args = ListContainersArgs.model_validate_json(raw_arguments)
                        mgr = _resolve_manager(args.server_name)
                        if isinstance(mgr, str):
                            tool_output = mgr
                        else:
                            tool_output = f"[{args.server_name}]\n" + mgr.list_containers()

                    elif function_name == "get_container_logs":
                        args = GetContainerLogsArgs.model_validate_json(raw_arguments)
                        mgr = _resolve_manager(args.server_name)
                        if isinstance(mgr, str):
                            tool_output = mgr
                        else:
                            tool_output = mgr.get_container_logs(
                                container_name=args.container_name,
                                lines=args.lines
                            )

                    elif function_name == "restart_container":
                        args = RestartContainerArgs.model_validate_json(raw_arguments)
                        mgr = _resolve_manager(args.server_name)
                        if isinstance(mgr, str):
                            tool_output = mgr
                        else:
                            tool_output = mgr.restart_container(
                                container_name=args.container_name
                            )

                    elif function_name == "wait":
                        args = WaitArgs.model_validate_json(raw_arguments)
                        tool_output = docker_managers[next(iter(docker_managers))].wait(
                            seconds=args.seconds
                        )

                    elif function_name == "inspect_container":
                        args = InspectContainerArgs.model_validate_json(raw_arguments)
                        mgr = _resolve_manager(args.server_name)
                        if isinstance(mgr, str):
                            tool_output = mgr
                        else:
                            tool_output = mgr.inspect_container(
                                container_name=args.container_name
                            )

                    elif function_name == "check_disk_space":
                        args = CheckDiskSpaceArgs.model_validate_json(raw_arguments)
                        mgr = _resolve_manager(args.server_name)
                        if isinstance(mgr, str):
                            tool_output = mgr
                        else:
                            tool_output = mgr.check_disk_space()

                    else:
                        tool_output = f"Error: Tool {function_name} does not exist."

                except ValidationError as e:
                    print(f"⚠️ Agent hallucinated bad arguments. Sending error back to correct it.")
                    tool_output = f"Validation Error in your arguments. Please fix them and try again:\n{str(e)}"
                except Exception as e:
                    tool_output = f"Unexpected execution error: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_output
                })
                
            continue
            
        if response_message.content:
            return response_message.content

def main():
    print("====================================================")
    print("   Welcome to Docker AI Manager Interactive Chat  ")
    print("   Type 'exit' or 'quit' to end the session.        ")
    print("====================================================\n")

    session_history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    while True:
        try:
            user_input = input("👤 You: ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
                
            if not user_input:
                continue

            session_history.append({"role": "user", "content": user_input})
            final_answer = interact_with_agent(
                session_history, 
                active_tools=ORCHESTRATOR_TOOLS, 
                model_name="gpt-5.5"
            )
            print(f"\n🤖 [Orchestrator]:\n{final_answer}\n")

        except KeyboardInterrupt:
            print("\nSession interrupted. Goodbye!")
            break

if __name__ == "__main__":
    main()