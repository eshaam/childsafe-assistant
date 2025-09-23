from fabric import Connection, task 
import os
from pathlib import Path

# Configuration
APP_NAME = "childsafe-multi-agent-rag"
REMOTE_HOST = "156.155.253.118"
REMOTE_USER = "deploy"
REMOTE_PATH = f"/home/deploy/{APP_NAME}"
REPO_URL = f"https://github.com/eshaam/{APP_NAME}"
SSH_KEY_PATH = "~/.ssh/id_rsa"  # Default SSH key path


@task
def deploy(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
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
                conn.run("git pull origin master")
            except:
                print("🔄 Cloning repository...")
                conn.run(f"git clone {REPO_URL}.git .")

            # Backend deployment
            print("🐍 Setting up Python backend...")
            with conn.cd("backend"):
                # Create virtual environment if it doesn't exist
                conn.run("python3 -m venv venv || true")

                # Install dependencies with timeout and better options
                conn.run("venv/bin/pip install --upgrade pip")
                conn.run("venv/bin/pip install -r requirements.txt --timeout 300 --no-cache-dir")

                # Create necessary directories
                conn.run("mkdir -p config models logs")

                # Copy environment file if it doesn't exist
                result = conn.run("test -f .env", warn=True)
                if result.failed:
                    conn.run("cp .env.example .env")
                    print("⚠️  Please update .env file with production settings")

            # Frontend deployment
            print("⚛️  Building React frontend...")
            with conn.cd("frontend"):
                conn.run("npm install")

                # Build for production
                conn.run("npm run build")

            conn.run(f"pm2 restart {APP_NAME}")
            conn.run("pm2 save")
            
            print("✅ Deployment completed successfully!")



@task
def setup(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH, sudo_pass=None):
    """Initial server setup"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    
    # Configure sudo settings
    sudo_config = {}
    if sudo_pass:
        sudo_config["password"] = sudo_pass
    
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        # Set sudo configuration on the connection
        conn.config.sudo.password = sudo_pass if sudo_pass else None
        print("🛠️  Setting up server...")

        # Install PM2 for process management
        conn.sudo("npm install -g pm2")

        # Create application directory
        conn.sudo(f"mkdir -p {REMOTE_PATH}")
        conn.sudo(f"chown {user}:{user} {REMOTE_PATH}")

        print("✅ Server setup completed!")

@task
def restart_services(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
    """Restart application services"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        restart_services(conn)


def restart_services(conn):
    """Helper function to restart services"""
    with conn.cd(f"{REMOTE_PATH}/backend"):
        # Stop existing processes
        conn.run(f"pm2 delete {APP_NAME} || true", warn=True)

        # Start the application
        conn.run(f"pm2 start 'venv/bin/python -m app.main' --name {APP_NAME}")

        # Save PM2 configuration
        conn.run("pm2 save")
        conn.run("pm2 startup || true", warn=True)


@task
def logs(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
    """View application logs"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run(f"pm2 logs {APP_NAME}")


@task
def status(c, host=REMOTE_HOST, user=REMOTE_USER, key_path=SSH_KEY_PATH):
    """Check application status"""
    connect_kwargs = {"key_filename": os.path.expanduser(key_path)}
    with Connection(f"{user}@{host}", connect_kwargs=connect_kwargs) as conn:
        conn.run("pm2 status")


