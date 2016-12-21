# /etc/cron.d/dehydrated: crontab entries for dehydrated
#
# certbot recommends attempting renewal twice a day. we do the same
#
# Eventually, this will be an opportunity to validate certificates
# haven't been revoked, etc.  Renewal will only occur if expiration
# is within 30 days.
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

0 */12 * * * root test ! -e /etc/dehydrated/domains.txt || (perl -e 'sleep int(rand(3600))' && chronic /usr/bin/dehydrated -c)
