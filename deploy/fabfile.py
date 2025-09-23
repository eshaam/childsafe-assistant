from fabric import Connection, task
import os

# Configuration
APP_NAME = "childsafe-assistant"
REMOTE_HOST = "156.155.253.118"
REMOTE_USER = "deploy"
REMOTE_PATH = f"/home/deploy/{APP_NAME}"
REPO_URL = f"git@github.com:eshaam/{APP_NAME}.git"
SSH_KEY_PATH = "~/.ssh/id_rsa"  # Default SSH key path

# uv binary path (installed in ~/.local/bin by default)
UV_BIN = "~/.local/bin/uv"

# Default port (can be overridden in tasks)
DEFAULT_PORT = 8888


@task
def deploy(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Deploy the application to the remote server"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        print("🚀 Starting deployment...")

        # Create directory if it doesn't exist
        conn.run(f"mkdir -p {REMOTE_PATH}")

        # Navigate to project directory
        with conn.cd(REMOTE_PATH):
            # Pull latest code
            print("📥 Pulling latest code...")
            try:
                conn.run("git pull origin main")
            except:
                print("🔄 Cloning repository...")
                conn.run(f"git clone {REPO_URL} .")

            # Backend deployment
            print("🐍 Setting up Python backend with uv...")
            with conn.cd("backend"):
                conn.run(f"{UV_BIN} sync --frozen")
                conn.run("mkdir -p config models logs")

                result = conn.run("test -f .env", warn=True)
                if result.failed:
                    conn.run("cp .env.example .env")
                    print("⚠️  Please update .env file with production settings")

            # Frontend deployment
            print("⚛️  Building React frontend...")
            with conn.cd("frontend"):
                conn.run("npm install")
                conn.run("npm run build")

            restart_services(conn, port)

            print("✅ Deployment completed successfully!")


@task
def setup(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, sudo_pass=None):
    """Initial server setup"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}

    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.config.sudo.password = sudo_pass if sudo_pass else None
        print("🛠️  Setting up server...")

        # Install uv if not installed
        conn.run("curl -LsSf https://astral.sh/uv/install.sh | sh || true")
        conn.run("mkdir -p ~/.local/bin")
        conn.run("echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc")

        # Install PM2 for process management
        conn.sudo("npm install -g pm2")

        # Create application directory
        conn.sudo(f"mkdir -p {REMOTE_PATH}")
        conn.sudo(f"chown {user}:{user} {REMOTE_PATH}")

        print("✅ Server setup completed!")


@task
def restart_services(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """Restart application services"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        restart_services(conn, port)


def restart_services(conn, port):
    """Helper function to restart services on a specific port"""
    process_name = f"{APP_NAME}-{port}"
    with conn.cd(f"{REMOTE_PATH}/backend"):
        conn.run(f"pm2 delete {process_name} || true", warn=True)
        conn.run(
            f"pm2 start '{UV_BIN} run -m app.api --port {port}' --name {process_name}"
        )
        conn.run("pm2 save")
        conn.run("pm2 startup || true", warn=True)


@task
def logs(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, port=DEFAULT_PORT):
    """View application logs"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    process_name = f"{APP_NAME}-{port}"
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run(f"pm2 logs {process_name}")


@task
def status(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
    """Check application status"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run("pm2 status")
