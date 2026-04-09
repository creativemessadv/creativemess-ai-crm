module.exports = {
  apps: [
    {
      name: 'outreach-daily',
      script: 'run_outreach.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 8 * * *',   // ogni giorno alle 08:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'scraper-daily',
      script: 'run_scraper.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 7 * * *',   // ogni giorno alle 07:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'report-mattina',
      script: 'run_report_mattina.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 13 * * *',  // ogni giorno alle 13:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'report-sera',
      script: 'run_report_sera.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 19 * * *',  // ogni giorno alle 19:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    },
    {
      name: 'briefing-settimanale',
      script: 'run_report_weekly.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      cron_restart: '0 7 * * 1',   // ogni lunedì alle 07:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    }
  ]
}
