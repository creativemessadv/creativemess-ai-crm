module.exports = {
  apps: [
    {
      name: 'outreach-daily',
      script: 'run_outreach.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 6 * * *',   // 08:00 ora italiana (UTC+2)
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'scraper-daily',
      script: 'run_scraper.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 5 * * *',   // 07:00 ora italiana (UTC+2)
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'report-mattina',
      script: 'run_report_mattina.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 11 * * *',  // 13:00 ora italiana (UTC+2)
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'report-sera',
      script: 'run_report_sera.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 17 * * *',  // 19:00 ora italiana (UTC+2)
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'briefing-settimanale',
      script: 'run_report_weekly.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 5 * * 1',   // lunedì 07:00 ora italiana (UTC+2)
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    }
  ]
}
