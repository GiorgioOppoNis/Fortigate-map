#!/usr/bin/env python3

import csv
import json
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings()

# ==================================================
# CONFIGURAZIONE
# ==================================================

ZABBIX_URL = "http://10.211.100.14/zabbix/api_jsonrpc.php"

# API TOKEN GENERATO DA:
# Administration -> API tokens
ZABBIX_TOKEN = "d3215aee7429c6b8181909ae3c32a92330e51e2c8191343d973d262895ce68b1"

CSV_FILE = "test.csv"

HOST_GROUP_NAME = "Firewall"

FORTIGATE_TEMPLATE_ID = "10604"


# ============================================================
# SSL
# ============================================================

urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(
    InsecureRequestWarning
)

# ============================================================
# API CALL
# ============================================================

def zabbix_api(method, params):

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }

    headers = {
        "Authorization": f"Bearer {ZABBIX_TOKEN}",
        "Content-Type": "application/json-rpc"
    }

    response = requests.post(
        ZABBIX_URL,
        json=payload,
        headers=headers,
        verify=False,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:

        print("\n===== ERRORE COMPLETO ZABBIX =====")
        print(json.dumps(data, indent=2))
        print("==================================\n")

        raise Exception(data["error"])

    return data["result"]

# ============================================================
# HOST GROUP
# ============================================================

def get_group_id(group_name):

    result = zabbix_api(
        "hostgroup.get",
        {
            "output": ["groupid", "name"],
            "filter": {
                "name": [group_name]
            }
        }
    )

    if not result:
        raise Exception(
            f"Host Group '{group_name}' non trovato"
        )

    return result[0]["groupid"]

def get_template_id(template_name):

    result = zabbix_api(
        "template.get",
        {
            "output": ["templateid", "host"],
            "filter": {
                "host": [template_name]
            }
        }
    )

    if not result:
        raise Exception(
            f"Template '{template_name}' non trovato"
        )

    return result[0]["templateid"]

# ============================================================
# HOST ESISTENTE
# ============================================================

def host_exists(hostname):

    result = zabbix_api(
        "host.get",
        {
            "filter": {
                "host": [hostname]
            }
        }
    )

    return len(result) > 0

# ============================================================
# CREAZIONE HOST
# ============================================================

import json

SNMPV3_USER = "zbxmonusr"
SNMPV3_AUTH_PASSWORD = "#E#mVX!IV;O*WZ*vnHBw"
SNMPV3_PRIV_PASSWORD = "7=&yBDmfsw!,WN@3@;ax"

def create_host(
    hostname,
    ip,
    group_ids,
    template_ids
):

    payload = {
        "host": hostname,

        "groups": [
            {
                "groupid": str(group_id)
            }
            for group_id in group_ids
        ],

        "interfaces": [
            {
                "type": 2,
                "main": 1,
                "useip": 1,
                "ip": ip,
                "dns": "",
                "port": "161",
                "details": {
                    "version": 3,
                    "bulk": 1,
                    "securityname": SNMPV3_USER,
                    "securitylevel": 2,
                    "authprotocol": 1,
                    "authpassphrase": SNMPV3_AUTH_PASSWORD,
                    "privprotocol": 1,
                    "privpassphrase": SNMPV3_PRIV_PASSWORD
                }
            }
        ]
    }

    if template_ids:
        payload["templates"] = [
            {
                "templateid": str(template_id)
            }
            for template_id in template_ids
        ]

    print("\n===== PAYLOAD HOST.CREATE =====")
    print(json.dumps(payload, indent=2))
    print("===============================\n")

    return zabbix_api(
        "host.create",
        payload
    )
def list_templates():

    result = zabbix_api(
        "template.get",
        {
            "output": ["templateid", "host"]
        }
    )

    print("\n=== TEMPLATE DISPONIBILI ===")

    for t in sorted(result, key=lambda x: x["host"]):
        print(f"{t['templateid']} - {t['host']}")
# ============================================================
# IMPORT CSV
# ============================================================
def get_or_create_hostgroup(group_name):

    result = zabbix_api(
        "hostgroup.get",
        {
            "filter": {
                "name": [group_name]
            }
        }
    )

    if result:
        return result[0]["groupid"]

    print(
        f"[INFO] Creo Host Group: "
        f"{group_name}"
    )

    result = zabbix_api(
        "hostgroup.create",
        {
            "name": group_name
        }
    )

    return result["groupids"][0]

def import_csv():
    FORTIGATE_TEMPLATE_ID = get_template_id(
        "FortiGate by SNMP"
    )
    print("[INFO] Recupero Host Group...")

    #
    # LETTURA CSV
    #
    with open(
        CSV_FILE,
        mode="r",
        encoding="utf-8-sig",
        newline=""
    ) as csvfile:

        reader = csv.DictReader(
            csvfile,
            delimiter=";"
        )

        print(
            f"[INFO] Colonne CSV trovate: "
            f"{reader.fieldnames}"
        )

        rows = [
            row for row in reader
            if row.get("Hostname", "").strip()
        ]

    #
    # PRE ANALISI
    #
    total_hosts = 0
    existing_hosts = 0
    new_hosts = 0

    print("\n[INFO] Analisi host presenti in Zabbix...\n")

    for row in rows:

        hostname = row.get(
            "Hostname",
            ""
        ).strip()

        ip = row.get(
            "Management IP",
            ""
        ).strip()

        if not hostname or not ip:
            continue

        total_hosts += 1

        try:

            if host_exists(hostname):
                existing_hosts += 1
            else:
                new_hosts += 1

        except Exception as e:

            print(
                f"[WARNING] Errore verifica "
                f"{hostname}: {e}"
            )

    print("=" * 60)
    print("ANALISI PRELIMINARE")
    print("=" * 60)
    print(f"Host validi nel CSV : {total_hosts}")
    print(f"Già presenti        : {existing_hosts}")
    print(f"Da aggiungere       : {new_hosts}")
    print("=" * 60)
    print()

    #
    # TEMPLATE FORTIGATE
    #


    total = 0
    created = 0
    skipped = 0
    errors = 0

    for row in rows:

        total += 1

        hostname = row.get(
            "Hostname",
            ""
        ).strip()

        management_ip = row.get(
            "Management IP",
            ""
        ).strip()

        adom = row.get(
            "ADOM",
            ""
        ).strip()

        area_vasta = row.get(
            "Area Vasta",
            ""
        ).strip()

        try:

            #
            # HOST ESISTENTE
            #
            if host_exists(hostname):

                print(
                    f"[SKIP] Host già presente: "
                    f"{hostname}"
                )

                skipped += 1
                continue

            #
            # HOST GROUPS
            #
            firewall_group_id = get_or_create_hostgroup(
                "Firewall"
            )

            adom_group_id = get_or_create_hostgroup(
                adom
            )

            area_group_id = get_or_create_hostgroup(
                area_vasta
            )

            group_ids = [
                firewall_group_id,
                adom_group_id,
                area_group_id
            ]

            #
            # TEMPLATE
            #
            template_ids = [
                FORTIGATE_TEMPLATE_ID
            ]

            #
            # CREA HOST
            #
            result = create_host(
                hostname,
                management_ip,
                group_ids,
                template_ids
            )

            hostid = result["hostids"][0]

            created += 1

            print(
                f"[OK] Creato "
                f"{hostname} "
                f"({management_ip}) "
                f"HostID={hostid}"
            )

        except Exception as e:

            errors += 1

            print(
                f"[ERRORE] {hostname}: {e}"
            )

    print()
    print("=" * 60)
    print("IMPORT COMPLETATO")
    print("=" * 60)
    print(f"Host CSV           : {total_hosts}")
    print(f"Già presenti       : {existing_hosts}")
    print(f"Nuovi previsti     : {new_hosts}")
    print("-" * 60)
    print(f"Creati             : {created}")
    print(f"Saltati            : {skipped}")
    print(f"Errori             : {errors}")
    print("=" * 60)



# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    list_templates()
    import_csv()