from fabric import Connection, task
import os

# Configuration
APP_NAME = "childsafe-assistant"
REMOTE_HOST = "156.155.253.118"
REMOTE_USER = "deploy"
REMOTE_PATH = f"/home/deploy/{APP_NAME}"
REPO_URL = f"git@github.com:eshaam/{APP_NAME}.git"
SSH_KEY_PATH = "~/.ssh/id_rsa"

UV_BIN = "~/.local/bin/uv"
DEFAULT_PORT = 8888


@task
def deploy(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Deploy the application to the remote server"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        print("🚀 Starting deployment...")

        # Ensure project directory exists
        conn.run(f"mkdir -p {REMOTE_PATH}")

        with conn.cd(REMOTE_PATH):
            # Pull latest code
            print("📥 Pulling latest code...")
            result = conn.run("git pull origin main", warn=True)
            if result.failed:
                print("🔄 Cloning repository...")
                conn.run(f"git clone {REPO_URL} .")

            # Backend
            print("🐍 Setting up Python backend with uv...")
            with conn.cd("backend"):
                conn.run(f"{UV_BIN} sync --frozen")
                conn.run("mkdir -p config models logs")
                env_check = conn.run("test -f .env", warn=True)
                if env_check.failed:
                    conn.run("cp .env.example .env")
                    print("⚠️  Please update .env file with production settings")

            # Frontend
            print("⚛️  Building React frontend...")
            with conn.cd("frontend"):
                conn.run("npm install")
                conn.run("npm run build")

            # Restart services (clean)
            restart_services(conn, port)
            print("✅ Deployment completed successfully!")


@task
def setup(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, sudo_pass=None):
    """Initial server setup"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.config.sudo.password = sudo_pass if sudo_pass else None
        print("🛠️  Setting up server...")

        # Install uv
        conn.run("curl -LsSf https://astral.sh/uv/install.sh | sh || true")
        conn.run("mkdir -p ~/.local/bin")
        conn.run("echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc")

        # Install PM2
        conn.sudo("npm install -g pm2")

        # Create app directory
        conn.sudo(f"mkdir -p {REMOTE_PATH}")
        conn.sudo(f"chown {user}:{user} {REMOTE_PATH}")

        print("✅ Server setup completed!")


def restart_services(conn, port):
    """Restart the app via PM2 (production-safe)"""
    process_name = f"{APP_NAME}-{port}"
    
    # FIX: Correct uvicorn command syntax
    # Using 'uv run uvicorn' instead of 'uv run -m'
    uvicorn_cmd = f"/home/deploy/.local/bin/uv run uvicorn app.api:app --host 0.0.0.0 --port {port}"

    with conn.cd(f"{REMOTE_PATH}/backend"):
        # Delete any old errored processes
        conn.run(f"pm2 delete {process_name} || true", warn=True)

        # Start Uvicorn with PM2 fork mode
        conn.run(
            f"pm2 start '{uvicorn_cmd}' "
            f"--name {process_name} "
            f"--watch false "
            f"--merge-logs "
            f"--log-date-format='YYYY-MM-DD HH:mm:ss' "
            f"--cwd {REMOTE_PATH}/backend"  # Ensure correct working directory
        )

        # Save PM2 state
        conn.run("pm2 save")

        # Ensure PM2 startup is configured
        conn.run("pm2 startup || true", warn=True)

        # Show process status
        conn.run(f"pm2 status {process_name}")


@task
def logs(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT, lines=50):
    """View application logs"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    process_name = f"{APP_NAME}-{port}"
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run(f"pm2 logs {process_name} --lines {lines}")


@task
def status(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
    """Check application status"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run("pm2 status")


@task
def restart(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Restart the application without full deployment"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        with conn.cd(REMOTE_PATH):
            restart_services(conn, port)
            print("✅ Application restarted!")


@task
def stop(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Stop the application"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    process_name = f"{APP_NAME}-{port}"
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run(f"pm2 stop {process_name}")
        print(f"⏹️  Stopped {process_name}")


@task
def debug(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Run the application directly (not via PM2) for debugging"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        with conn.cd(f"{REMOTE_PATH}/backend"):
            # Run directly to see full output
            conn.run(f"{UV_BIN} run uvicorn app.api:app --host 0.0.0.0 --port {port}")