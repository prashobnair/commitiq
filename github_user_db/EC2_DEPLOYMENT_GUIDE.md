# EC2 Deployment Guide for GitHub User Collection

This guide provides step-by-step instructions for deploying and running the GitHub user collection script on an EC2 instance with RDS PostgreSQL.

## Prerequisites

1. An AWS account with permissions to:
   - Create and manage EC2 instances
   - Create and manage RDS PostgreSQL instances
   - Create and manage security groups

2. A GitHub personal access token (optional but recommended to avoid rate limits)

## Step 1: Set Up RDS PostgreSQL Instance

1. **Log in to the AWS Management Console** and navigate to the RDS service.

2. **Create a new PostgreSQL database**:
   - Click "Create database"
   - Select "Standard create"
   - Choose "PostgreSQL" as the engine type
   - Select the appropriate version (11 or higher recommended)
   - Choose a DB instance identifier (e.g., `github-users-db`)
   - Set up master username and password (save these securely)
   - Choose an appropriate instance size (t3.micro for testing, larger for production)
   - Configure storage (20GB minimum recommended, enable autoscaling)
   - Set up VPC, subnet group, and security group (ensure it allows inbound connections on port 5432 from your EC2 instance)
   - Create the database

3. **Create a database**:
   - Connect to the RDS instance using a PostgreSQL client
   - Create a database named `github_users` (or your preferred name)

## Step 2: Launch an EC2 Instance

1. **Navigate to the EC2 service** in the AWS Management Console.

2. **Launch a new EC2 instance**:
   - Click "Launch instance"
   - Choose an Amazon Linux 2 AMI
   - Select an appropriate instance type (t2.micro for testing, t2.medium or larger for production)
   - Configure instance details (use default VPC or the same VPC as your RDS instance)
   - Add storage (at least 8GB recommended)
   - Configure security group to allow SSH access (port 22) from your IP
   - Launch the instance and select/create a key pair

3. **Connect to your EC2 instance** using SSH:
   ```bash
   ssh -i /path/to/your-key.pem ec2-user@your-instance-public-dns
   ```

## Step 3: Set Up the Environment on EC2

1. **Update the system and install dependencies**:
   ```bash
   sudo yum update -y
   sudo yum install -y git python3 python3-pip python3-devel postgresql-devel gcc
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/commitiq.git
   cd commitiq/github_user_db
   ```

3. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**:
   ```bash
   cp .env.template .env
   nano .env  # Edit with your actual values
   ```

   Update the `.env` file with:
   - Your GitHub token
   - RDS endpoint and credentials
   - Any other configuration parameters

## Step 4: Run the Collection Script

1. **Test the connection to the database**:
   ```bash
   python -c "from db_postgres import init_db_pool, init_db, close_db_pool; init_db_pool(); init_db(); close_db_pool()"
   ```

2. **Run the script**:
   ```bash
   python collect_users_rds.py
   ```

   Or with explicit parameters:
   ```bash
   python collect_users_rds.py --workers 10 --batch-size 100 --db-host your-rds-endpoint.region.rds.amazonaws.com --db-name github_users --db-user your_username --db-password your_password
   ```

## Step 5: Set Up for Long-Running Collection

For long-running collection that continues even after you disconnect from the EC2 instance:

1. **Install screen or tmux**:
   ```bash
   sudo yum install -y screen
   ```

2. **Start a screen session**:
   ```bash
   screen -S github-collection
   ```

3. **Run the collection script**:
   ```bash
   cd ~/commitiq/github_user_db
   source venv/bin/activate
   python collect_users_rds.py
   ```

4. **Detach from the screen session** (the script will continue running):
   Press `Ctrl+A` followed by `D`

5. **To reattach to the session later**:
   ```bash
   screen -r github-collection
   ```

## Step 6: Set Up Automatic Startup (Optional)

To automatically start the collection script when the EC2 instance boots:

1. **Create a systemd service file**:
   ```bash
   sudo nano /etc/systemd/system/github-collection.service
   ```

2. **Add the following content**:
   ```
   [Unit]
   Description=GitHub User Collection Service
   After=network.target

   [Service]
   Type=simple
   User=ec2-user
   WorkingDirectory=/home/ec2-user/commitiq/github_user_db
   ExecStart=/home/ec2-user/commitiq/github_user_db/venv/bin/python /home/ec2-user/commitiq/github_user_db/collect_users_rds.py
   Restart=on-failure
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable github-collection
   sudo systemctl start github-collection
   ```

4. **Check the service status**:
   ```bash
   sudo systemctl status github-collection
   ```

## Monitoring and Maintenance

1. **Check the logs**:
   ```bash
   tail -f github_user_collection.log
   ```

2. **Monitor system resources**:
   ```bash
   top
   ```

3. **Monitor disk usage**:
   ```bash
   df -h
   ```

4. **Set up CloudWatch monitoring** (optional):
   - Navigate to the CloudWatch service in the AWS Management Console
   - Set up alarms for CPU, memory, and disk usage
   - Configure notifications for when thresholds are exceeded

## Troubleshooting

1. **Database connection issues**:
   - Verify that the security group for your RDS instance allows inbound connections from your EC2 instance
   - Check that the database credentials in your `.env` file are correct
   - Ensure the database exists and the user has appropriate permissions

2. **GitHub API rate limiting**:
   - Use a GitHub token to increase your rate limit
   - Adjust the number of workers to avoid hitting rate limits
   - Check the logs for rate limit warnings

3. **Script crashes or stops running**:
   - Check the logs for error messages
   - Ensure you have enough memory and disk space
   - Consider using a larger EC2 instance if needed

## Security Considerations

1. **Protect your GitHub token and database credentials**:
   - Never commit them to version control
   - Use environment variables or a secure parameter store
   - Restrict access to the `.env` file

2. **Secure your EC2 instance**:
   - Keep the system updated
   - Use a strong SSH key
   - Restrict SSH access to trusted IP addresses
   - Consider using AWS Systems Manager Session Manager instead of direct SSH

3. **Secure your RDS instance**:
   - Use a strong password
   - Restrict access to only necessary IP addresses/security groups
   - Enable encryption at rest
   - Regularly back up your database

## Cost Optimization

1. **Choose appropriate instance sizes**:
   - Start with smaller instances and scale up as needed
   - Consider using spot instances for non-critical workloads

2. **Monitor and optimize database usage**:
   - Use RDS monitoring to track performance
   - Consider scaling down during periods of low activity

3. **Set up budget alerts** to avoid unexpected costs

## Next Steps

1. **Analyze the collected data**:
   - Set up data analysis tools
   - Create dashboards and reports

2. **Automate the process**:
   - Set up scheduled tasks to run the collection script
   - Implement monitoring and alerting

3. **Scale the solution**:
   - Consider using multiple EC2 instances for parallel collection
   - Implement a queue-based architecture for better scalability 