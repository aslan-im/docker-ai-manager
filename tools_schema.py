from pydantic import BaseModel, Field
from openai import pydantic_function_tool


class ListContainersArgs(BaseModel):
    server_name: str = Field(..., description="Name of the target server as defined in config (e.g. 'thinkpad', 'raspi')")

class GetContainerLogsArgs(BaseModel):
    server_name: str = Field(..., description="Name of the target server as defined in config (e.g. 'thinkpad', 'raspi')")
    container_name: str = Field(..., description="The name or ID of the target container")
    lines: int = Field(default=20, description="Number of log lines to retrieve (default is 20)")

class RestartContainerArgs(BaseModel):
    server_name: str = Field(..., description="Name of the target server as defined in config (e.g. 'thinkpad', 'raspi')")
    container_name: str = Field(..., description="The name or ID of the container to restart")

class WaitArgs(BaseModel):
    seconds: int = Field(..., description="Number of seconds to wait (e.g., 5 or 10)")

class InspectContainerArgs(BaseModel):
    server_name: str = Field(..., description="Name of the target server as defined in config (e.g. 'thinkpad', 'raspi')")
    container_name: str = Field(..., description="The name or ID of the container to inspect")

class CheckDiskSpaceArgs(BaseModel):
    server_name: str = Field(..., description="Name of the target server as defined in config (e.g. 'thinkpad', 'raspi')")

tools_schema = [
    pydantic_function_tool(
        model=ListContainersArgs,
        name="list_containers",
        description="Returns a list of all containers on the specified remote server, their status, and names. Use this tool whenever you need to check the infrastructure state."
    ),
    pydantic_function_tool(
        model=GetContainerLogsArgs,
        name="get_container_logs",
        description="Returns the last N lines of logs for a specific container on the specified server. Use this if a container is down or misbehaving to find the root cause."
    ),
    pydantic_function_tool(
        model=RestartContainerArgs,
        name="restart_container",
        description="Restarts the specified container on the specified remote server. CRITICAL: After calling this, you MUST call the 'wait' tool for at least 5 seconds BEFORE checking the logs, to give the application time to boot."
    ),
    pydantic_function_tool(
        model=WaitArgs,
        name="wait",
        description="Pauses execution for a specified number of seconds. Use this tool AFTER restarting a service to give it time to boot UP BEFORE checking its logs. If logs are empty, you can wait again."
    ),
    pydantic_function_tool(
        model=InspectContainerArgs,
        name="inspect_container",
        description="Returns detailed configuration (docker inspect) for a container on the specified server. Use this to find network modes (e.g., container:gluetun dependencies), volume mounts, port mappings, and detailed state."
    ),
    pydantic_function_tool(
        model=CheckDiskSpaceArgs,
        name="check_disk_space",
        description="Checks the disk space on the specified remote server. Use this tool to check if the disk is full or has enough space."
    )
]
