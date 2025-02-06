2. Make the Script Executable
Run the following command to make the script executable:

bash
Copy code
chmod +x /home/server/exercise-db/backup.sh


Schedule the Script Using cron
Set up a cron job to run the backup script periodically. For example, to run the backup daily at 2:00 AM:

bash
Copy code
crontab -e
Add the following line to schedule the backup:

bash
Copy code
0 2 * * * /home/server/exercise-db/backup.sh
Save and exit.