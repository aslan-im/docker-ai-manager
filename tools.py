import docker
import os
import time

class RemoteDockerManager:
    def __init__(self, name: str, host: str, username: str, key_filename: str = None):
        self.name = name
        self.host = host
        self.username = username
        self.key_filename = key_filename
        self.client = None

    def _get_client(self):
        """Lazy initialization of the Docker SDK client over SSH"""
        if self.client is None:
            # Construct standard SSH connection string for Docker SDK
            # Example: ssh://n0mad@192.168.0.10
            base_url = f"ssh://{self.username}@{self.host}"
            
            # The docker library automatically picks up keys from your ssh-agent.
            # If you need a specific key, we can pass it via environment variables 
            # that the docker/ssh subsystem respects under the hood.
            if self.key_filename:
                os.environ["SSH_AUTH_SOCK"] = "" # Forces usage of explicit key if needed
                
            self.client = docker.DockerClient(base_url=base_url, use_ssh_client=True)
        return self.client

    def list_containers(self) -> str:
        """
        Returns a list of all containers on the remote server, their status, and names.
        Use this tool whenever you need to check the infrastructure state.
        """
        try:
            client = self._get_client()
            # Fetch all containers (including stopped ones)
            containers = client.containers.list(all=True)
            
            if not containers:
                return "No containers found on the remote server."
            
            result = []
            for c in containers:
                result.append(f"Name: {c.name} | Status: {c.status} | Image: {c.image.tags}")
            
            return "\n".join(result)
        except Exception as e:
            return f"Error listing containers: {str(e)}"

    def get_container_logs(self, container_name: str, lines: int = 20) -> str:
        """
        Returns the last N lines of logs for a specific container.
        Use this if a container is down or misbehaving to find the root cause.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_name)
            
            # Fetch logs as bytes, decode to string
            logs = container.logs(tail=int(lines), stdout=True, stderr=True)
            output = logs.decode('utf-8')
            
            if not output.strip():
                return f"No logs found for container '{container_name}'."
                
            return output
        except docker.errors.NotFound:
            return f"Error: Container '{container_name}' not found."
        except Exception as e:
            return f"Error fetching logs: {str(e)}"

    def restart_container(self, container_name: str) -> str:
        """
        Restarts the specified container on the remote server.
        Use this only when necessary to reset state or apply a fix.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_name)
            container.restart()
            return f"Success: Container '{container_name}' has been restarted."
        except docker.errors.NotFound:
            return f"Error: Container '{container_name}' not found."
        except Exception as e:
            return f"Error restarting container: {str(e)}"
    
    def wait(self, seconds: int) -> str:
        """
        Pauses execution for the specified number of seconds.
        Use this after restarting a container to give it time to boot before checking logs.
        """
        delay = min(int(seconds), 30)
        print(f"⏳ System paused for {delay} seconds by agent request...")
        time.sleep(delay)
        return f"Success: Waited for {delay} seconds."
    
    def inspect_container(self, container_name: str) -> str:
        """
        Returns detailed configuration and state information for a specific container (docker inspect).
        Useful for checking environment variables, network modes (e.g., VPN dependencies), mounts, and exact state.
        """
        import json # just in case it's not imported at the top
        try:
            client = self._get_client()
            container = client.containers.get(container_name)
            attrs = container.attrs
            
            # Extracting only the most relevant parts to avoid token overflow
            relevant_info = {
                "Name": attrs.get("Name"),
                "State": attrs.get("State", {}),
                "Image": attrs.get("Config", {}).get("Image"),
                "NetworkMode": attrs.get("HostConfig", {}).get("NetworkMode"),
                "Ports": attrs.get("NetworkSettings", {}).get("Ports"),
                "Mounts": attrs.get("Mounts"), 
            }
            return json.dumps(relevant_info, indent=2)
        except docker.errors.NotFound:
            return f"Error: Container '{container_name}' not found."
        except Exception as e:
            return f"Error inspecting container: {str(e)}"
    
    def check_disk_space(self) -> str:
        image="alpine:latest"
        command="df -h"
        remove=True
        volumes = {
            '/': {
                'bind': '/host_root', 
                'mode': 'ro'
            }
        }
        try:
            client = self._get_client()
            
            container = client.containers.run(
                image="alpine:latest", 
                command="df -h", 
                detach=True, 
                volumes=volumes
            )
            
            container.wait()
            
            output = container.logs()
            
            container.remove()
            
            return output.decode('utf-8').strip()
        except Exception as e:
            return f"Error checking disk space: {str(e)}"


