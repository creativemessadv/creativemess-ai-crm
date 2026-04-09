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
      name: 'scraper-weekly',
      script: 'run_scraper.sh',
      interpreter: 'bash',
      cwd: '/root/agency/automation',
      args: '--settore ristoranti --citta Milano --n 100',
      cron_restart: '0 7 * * 1',   // ogni lunedì alle 07:00
      autorestart: false,
      watch: false,
      env: { HTTP_PROXY: '', HTTPS_PROXY: '' }
    }
  ]
}
