import subprocess
import sys
import time

import subprocess
import time


def wait_for_healthy(container_name, timeout=1200):
    start = time.time()

    while True:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
        )

        status = (
            result.stdout.strip()
        )  # contains whatever the command printed to the terminal (the standard output)

        if status == "healthy":
            print(f"{container_name} is healthy.")
            return

        if time.time() - start > timeout:
            raise TimeoutError(f"{container_name} not healthy in time!!!")

        print(f"Waiting for {container_name}... ({status})")
        time.sleep(60)


SERVERS = [
    "docker",
    "compose",
    "-f",
    "Servers/docker-compose.server.yml",
    "--env-file",
    "Servers/.env.server",
]

APP = [
    "docker",
    "compose",
    "-f",
    "docker-compose.app.yml",
    "--env-file",
    "src/.env.app",
]


def run(cmd):
    subprocess.run(cmd, check=True)


def up():

    print("Starting infrastructure...")
    run(SERVERS + ["up", "-d"])

    print("Waiting for infrastructure to be ready...")
    wait_for_healthy("postgres-server")
    wait_for_healthy("vllm-server")

    print("Building app (quiet)...")
    run(APP + ["build", "-q"])

    print("Starting app...")
    run(APP + ["run", "--rm", "-it", "app"])

    # attach()


def down():
    run(APP + ["down"])
    run(SERVERS + ["down"])


def attach():
    print("Please enter your query:")
    run(["docker", "attach", "banking-agent"])


def logs_app():
    run(APP + ["logs", "-f"])


def logs_servers():
    run(SERVERS + ["logs", "-f"])


def clean():
    run(APP + ["down", "-v", "--remove-orphans"])
    run(SERVERS + ["down", "-v", "--remove-orphans"])


commands = {
    "up": up,
    "down": down,
    "attach": attach,
    "logs-app": logs_app,
    "logs-servers": logs_servers,
    "clean": clean,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(f"Usage: python make.py <command>")
        print(f"Commands: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[sys.argv[1]]()
