#!/usr/bin/env python
#
# dnspython-hook - dns-01 Challenge Hook Script for dehydrated.sh
#
# This script uses the dnspython API to create and delete TXT records
# in order to prove ownership of a domain.
#
# Copyright (C) 2016 Elizabeth Ferdman https://eferdman.github.io
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################

# callbacks
# deploy_challenge <DOMAIN> <TOKEN_FILENAME> <TOKEN_VALUE>
# clean_challenge <DOMAIN> <FILENAME> <TOKEN_VALUE>
# deploy_cert <DOMAIN> <KEYFILE> <CERTFILE> <FULLCHAINFILE> <CHAINFILE> <TIMESTAMP>
# unchanged_cert DOMAIN> <KEYFILE> <CERTFILE> <FULLCHAINFILE> <CHAINFILE>


import os
import sys
import time
import logging
import dns.resolver
import dns.tsig
import dns.tsigkeyring
import dns.update
import dns.query
from dns.exception import DNSException

# Configure some basic logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

# the default config-file
configfile="dnspython.conf"


# Replace 10.0.0.1 with the IP address of your master server.
name_server_ip = '10.0.0.1'

# If necessary, replace HMAC_MD5
# with HMAC_SHA1, HMAC_SHA224, HMAC_SHA256, HMAC_SHA384, HMAC_SHA512
keyalgorithm = dns.tsig.HMAC_MD5


def get_key():
    import iscpy
    key_dict = {}
    try:
        import iscpy
    except ImportError:
        logging.exception("")
        logging.fatal("The 'iscpy' module is required to read keys from isc-config file."
                      "Alternatively set key_name/key_secret in the configuration file")
        sys.exit(1)
    key_file = os.environ.get('DDNS_HOOK_KEY_FILE')

    # Open the key file for reading
    try:
        f = open(key_file, 'rU')
    except IOError:
        logging.exception("Unable to read isc-config file")
        logging.fatal("Did you set the DDNS_HOOK_KEY_FILE env?"
                      "Alternatively set key_name/key_secret in the configuration file")
        sys.exit(1)

    # Parse the key file
    parsed_key_file = iscpy.ParseISCString(f.read())

    # Grab the keyname, cut out the substring "key "
    # and remove the extra quotes
    key_name = parsed_key_file.keys()[0][4:].strip('\"')

    # Grab the secret key
    secret = parsed_key_file.values()[0]['secret'].strip('\"')
    key_dict[key_name] = secret
    f.close()

    return key_dict


def read_config():
    import argparse
    try:
        import configparser
    except ImportError:
        import ConfigParser as configparser

    configfile="dnspython.conf"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config",
        help="Read options from configuration file [%s]" % (configfile),
        metavar="FILE")
    subparsers = parser.add_subparsers(help='sub-command help')

    parser_deploychallenge = subparsers.add_parser('deploy_challenge', help='make ACME challenge available via DNS')
    parser_deploychallenge.set_defaults(func=deploy_challenge)
    parser_deploychallenge.add_argument(
        'domain',
        nargs=1,
        help="domain name to request certificate for")
    parser_deploychallenge.add_argument(
        'tokenfile',
        nargs=1,
        help="IGNORED")
    parser_deploychallenge.add_argument(
        'token',
        nargs=1,
        help="ACME-provided token")

    parser_cleanchallenge = subparsers.add_parser('clean_challenge', help='remove ACME challenge from DNS')
    parser_cleanchallenge.set_defaults(func=clean_challenge)
    parser_cleanchallenge.add_argument(
        'domain',
        nargs=1,
        help="domain name for which to remove cetificate challenge")
    parser_cleanchallenge.add_argument(
        'tokenfile',
        nargs=1,
        help="IGNORED")
    parser_cleanchallenge.add_argument(
        'token',
        nargs=1,
        help="ACME-provided token")

    parser_deploycert = subparsers.add_parser('deploy_cert', help='deploy certificate obtained from ACME (IGNORED)')
    parser_deploycert.set_defaults(func=deploy_cert)
    parser_deploycert.add_argument(
        'domain',
        nargs=1,
        help="domain name to deploy certificate for")
    parser_deploycert.add_argument(
        'keyfile',
        nargs=1,
        help="private certificate")
    parser_deploycert.add_argument(
        'certfile',
        nargs=1,
        help="public certificate")
    parser_deploycert.add_argument(
        'fullchainfile',
        nargs=1,
        help="full certificate chain")
    parser_deploycert.add_argument(
        'chainfile',
        nargs=1,
        help="certificate chain")
    parser_deploycert.add_argument(
        'timestamp',
        nargs=1,
        help="time stamp")

    parser_unchangedcert = subparsers.add_parser('unchanged_cert', help='unchanged certificate obtained from ACME (IGNORED)')
    parser_unchangedcert.set_defaults(func=unchanged_cert)
    parser_unchangedcert.add_argument(
        'domain',
        nargs=1,
        help="domain name, for which the certificate hasn't changed")
    parser_unchangedcert.add_argument(
        'keyfile',
        nargs=1,
        help="private certificate")
    parser_unchangedcert.add_argument(
        'certfile',
        nargs=1,
        help="public certificate")
    parser_unchangedcert.add_argument(
        'fullchainfile',
        nargs=1,
        help="full certificate chain")
    parser_unchangedcert.add_argument(
        'chainfile',
        nargs=1,
        help="certificate chain")

    args = parser.parse_args()
    if args.config:
        configfile = args.config

    config = configparser.ConfigParser()
    config.read(configfile)

    return config

keyring = dns.tsigkeyring.from_text(get_key())


# Create a TXT record through the dnspython API
# Example code at
#  https://github.com/rthalley/dnspython/blob/master/examples/ddns.py
def create_txt_record(domain_name, token):

    logger.info(' + Creating TXT record "%s" for the domain _acme-challenge.%s'
                % (token, domain_name))
    update = dns.update.Update(
        domain_name,
        keyring=keyring,
        keyalgorithm=keyalgorithm)
    update.add('_acme-challenge', 300, 'TXT', token)

    # Attempt to add a TXT record
    try:
        response = dns.query.udp(update, name_server_ip, timeout=10)
    except DNSException as err:
        logger.error(err)

    # Wait for DNS record to propagate
    time.sleep(5)

    # Check if the TXT record was inserted
    try:
        answers = dns.resolver.query('_acme-challenge.' + domain_name, 'TXT')
    except DNSException as err:
        logger.error(err)
        sys.exit(1)
    else:
        txt_records = [txt_record.strings[0] for txt_record in answers]
        if token in txt_records:
            logger.info(" + TXT record successfully added!")
        else:
            logger.info(" + TXT record not added.")
            sys.exit(1)


# Delete the TXT record using the dnspython API
def delete_txt_record(domain_name, token):
    logger.info(' + Deleting TXT record "%s" for the domain _acme-challenge.%s'
                % (token, domain_name))

    # Retrieve the specific TXT record
    txt_record = dns.rdata.from_text(
        dns.rdataclass.IN,
        dns.rdatatype.TXT,
        token)

    # Attempt to delete the TXT record
    update = dns.update.Update(
        domain_name,
        keyring=keyring,
        keyalgorithm=keyalgorithm)
    update.delete('_acme-challenge', txt_record)
    try:
        reponse = dns.query.udp(update, name_server_ip, timeout=10)
    except DNSException as err:
        logger.error(err)

    # Wait for DNS record to propagate
    time.sleep(5)

    # Check if the TXT record was successfully removed
    try:
        answers = dns.resolver.query('_acme-challenge.' + domain_name, 'TXT')
    except DNSException as err:
        logger.error(err)
        sys.exit(1)
    else:
        txt_records = [txt_record.strings[0] for txt_record in answers]
        if token in txt_records:
            logger.info(" + TXT record not successfully deleted.")
            sys.exit(1)
        else:
            logger.info(" + TXT record successfully deleted.")


def main(hook_stage, domain_name, token):
    logger.info(" + Dnsupdate.py executing " + hook_stage)

    if hook_stage == 'deploy_challenge':
        create_txt_record(domain_name, token)
    if hook_stage == 'clean_challenge':
        delete_txt_record(domain_name, token)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[4])
