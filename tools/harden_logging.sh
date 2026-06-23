#!/usr/bin/env bash
#
# Cap log growth on a NetCoin seed so a chatty service cannot fill the disk.
# Bounds journald storage and rotates rsyslog logs by size (not just weekly).
# Run ON the seed as root/sudo. Idempotent — safe to re-run.
#
# Background: seeds were filling root with a multi-GB /var/log/syslog because the
# default rsyslog logrotate is weekly while session/apparmor churn writes GBs/day.
set -euo pipefail

# 1. Cap journald on-disk storage.
install -d /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-netcoin-cap.conf <<'EOF'
[Journal]
SystemMaxUse=200M
SystemMaxFileSize=50M
EOF
systemctl restart systemd-journald

# 2. Rotate rsyslog logs daily OR when they pass 100M, keeping 7 compressed.
cat > /etc/logrotate.d/rsyslog <<'EOF'
/var/log/syslog
/var/log/mail.log
/var/log/kern.log
/var/log/auth.log
/var/log/user.log
/var/log/cron.log
{
	rotate 7
	daily
	maxsize 100M
	missingok
	notifempty
	compress
	delaycompress
	sharedscripts
	postrotate
		/usr/lib/rsyslog/rsyslog-rotate
	endscript
}
EOF

# 3. Run logrotate hourly so the maxsize cap is enforced between daily runs.
cat > /etc/cron.hourly/logrotate-netcoin <<'EOF'
#!/bin/sh
/usr/sbin/logrotate /etc/logrotate.conf
exit 0
EOF
chmod +x /etc/cron.hourly/logrotate-netcoin

echo "log caps applied: journald<=200M; syslog rotates daily/100M (checked hourly)"
