import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
from datetime import datetime
from selenium.webdriver.common.keys import Keys
from getpass import getpass

FORTIMANAGERS = [

 ("10.211.0.1", 10443, "ASL1",  "Nord Ovest", "lo-mgmt-asl1-ms"),
    ("10.211.0.2", 10443, "ASL2",  "Nord Ovest", "lo-mgmt-asl2-lu"),
    ("10.211.0.3", 10444, "ASL3",  "Centro",     "lo-mgmt-asl3-pt"),
    ("10.211.0.4", 10443, "ASL4",  "Centro",     "lo-mgmt-asl4-po"),
    ("10.211.0.5", 10443, "ASL5",  "Nord Ovest", "lo-mgmt-asl5-pi"),
    ("10.211.0.6", 10443, "ASL6",  "Nord Ovest", "lo-mgmt-asl6-li"),
    ("10.211.0.7", 10443, "ASL7",  "Sud Est",    "lo-mgmt-asl7-si"),
    ("10.211.0.8", 10443, "ASL8",  "Sud Est",    "lo-mgmt-asl8-ar"),
    ("10.211.0.9", 10443, "ASL9",  "Sud Est",    "lo-mgmt-asl9-gr"),
    ("10.211.0.10",10443, "ASL10", "Centro",     "lo-mgmt-asl10-tix"),
    ("10.211.0.11",10443, "ASL11", "Centro",     "lo-mgmt-asl11-em"),
    ("10.211.0.12",10443, "ASL12", "Nord Ovest", "lo-mgmt-asl12-vi"),
    ("10.211.0.13",10443, "AOUC",  "Centro",     "lo-mgmt-aouc-fi"),
    ("10.211.0.14",10444, "AOUM",  "Centro",     "lo-mgmt-aoum-fi"),
    ("10.211.0.15",10443, "AOUP",  "Nord Ovest", "lo-mgmt-aoup-pi"),
    ("10.211.0.16",10443, "AOUS",  "Sud Est",    "lo-mgmt-aous-si"),
    ("10.211.0.18",10443,"ESTAR","Sud Est","lo-mgmt-estar-si"),
    ("10.211.0.19",10443,"co112","Centro","lo-mgmt-co112-fi"),  
    ("10.211.0.20",10443,"co118","Centro","lo-mgmt-co118-fi"),
    ("10.211.0.21",10444,"co118","Centro","lo-mgmt-co118-pt"),  
    ("10.211.0.22",10443,"co118","Nord Ovest","lo-mgmt-co118-vi"),
    ("10.211.0.23",10443,"co118","Nord Ovest","lo-mgmt-co118-li"),  
    ("10.211.0.24",10443,"MNG","Centro","lo-mgmt-utc-mav"),
    ("10.211.0.25",10443,"MNG","Sud ESt","lo-mgmt-se-mav"), 
    ("10.211.0.26",10443,"MNG","Nord Ovest","lo-mgmt-no-mav"),  
]


def wait(driver, timeout=30):
    return WebDriverWait(driver, timeout)


# --------------------------------------------------
# LOGIN MANUALE
# --------------------------------------------------

def login_fortimanager(
    driver,
    ip,
    port,
    username,
    password
):

    url = f"https://{ip}:{port}"

    print(
        f"\n[INFO] Apertura {url}"
    )

    driver.get(url)

    try:

        username_field = wait(driver, 30).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[type='text']"
                )
            )
        )

        username_field.clear()

        username_field.send_keys(
            username
        )

        password_field = driver.find_element(
            By.CSS_SELECTOR,
            "input[type='password']"
        )

        password_field.clear()

        password_field.send_keys(
            password
        )

        password_field.send_keys(
            Keys.ENTER
        )

        print(
            "[INFO] Credenziali inserite"
        )

    except Exception as e:

        print(
            f"[WARN] Login form non trovato: {e}"
        )

    print(
        "[INFO] Attendo caricamento GUI..."
    )

    wait(driver, 120).until(
        EC.presence_of_element_located(
            (
                By.CSS_SELECTOR,
                "button.pop-up-menu-hover-toggle-attached"
            )
        )
    )

    print(
        "[OK] Login effettuato"
    )

# --------------------------------------------------
# MENU FORTIGATE
# --------------------------------------------------

def open_firewall_dropdown(driver):

    print("\n[INFO] Apro menu FortiGate...")

    button = wait(driver, 60).until(
        EC.visibility_of_element_located(
            (
                By.CSS_SELECTOR,
                "button.pop-up-menu-hover-toggle-attached"
            )
        )
    )

    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});",
        button
    )

    time.sleep(2)

    try:

        driver.execute_script(
            "arguments[0].click();",
            button
        )

    except Exception:

        ActionChains(driver) \
            .move_to_element(button) \
            .click() \
            .perform()

    time.sleep(5)

    print("[OK] Menu FortiGate aperto")


# --------------------------------------------------
# ESTRAZIONE DATI FIREWALL
# --------------------------------------------------
def get_firewalls(driver):

    candidates = driver.find_elements(
        By.XPATH,
        "//span[contains(@class,'name') "
        "and starts-with(normalize-space(),'FGT-')]"
    )

    unique_firewalls = {}
    
    for element in candidates:

        try:

            hostname = element.text.strip()

            if not hostname:
                continue

            if hostname not in unique_firewalls:

                unique_firewalls[hostname] = element

        except Exception:
            pass

    print("\n===================================")
    print("ELENCO FIREWALL TROVATI")
    print("===================================")

    for idx, hostname in enumerate(
        sorted(unique_firewalls.keys()),
        start=1
    ):

        print(
            f"{idx:03d} - {hostname}"
        )

    print("===================================\n")

    return unique_firewalls


def dump_firewall_tooltips(
    driver,
    source_ip,
    adom,
    area_vasta,
    fmgr_hostname
):

    import re
    import time

    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        StaleElementReferenceException
    )

    print("\n[INFO] Ricerca firewall...")

    fw_elements = driver.find_elements(
        By.XPATH,
        "//span[contains(@class,'name') "
        "and starts-with(normalize-space(),'FGT-')]"
    )

    firewall_names = []

    for fw in fw_elements:

        try:

            name = fw.text.strip()

            if (
                name
                and name.startswith("FGT-")
                and name not in firewall_names
            ):

                firewall_names.append(name)

        except Exception:
            pass

    print(
        f"[INFO] Firewall trovati: {len(firewall_names)}"
    )

    for idx, name in enumerate(
        firewall_names,
        start=1
    ):

        print(
            f"{idx:03d} - {name}"
        )

    results = []
    failed_firewalls = []

    for idx, fw_name in enumerate(
        firewall_names,
        start=1
    ):

        print(
            f"\n[{idx}] Analizzo {fw_name}"
        )

        success = False

        for retry in range(5):

            try:

                print(
                    f"[INFO] Tentativo {retry + 1}/5"
                )

                target = wait(driver, 20).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//span[contains(@class,'name') "
                            f"and normalize-space()='{fw_name}']"
                        )
                    )
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    target
                )

                time.sleep(2)

                ActionChains(driver) \
                    .move_to_element(target) \
                    .pause(4) \
                    .perform()

                time.sleep(2)

                overlays = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".cdk-overlay-pane"
                )

                popup_text = None

                for overlay in overlays:

                    try:

                        text = overlay.get_attribute(
                            "textContent"
                        )

                        if (
                            text
                            and "Hostname" in text
                            and "Serial Number" in text
                            and "Management IP/FQDN" in text
                        ):

                            popup_text = text
                            break

                    except Exception:
                        pass

                if not popup_text:

                    raise Exception(
                        "Tooltip non trovato"
                    )

                popup_text = " ".join(
                    popup_text.split()
                )

                print(
                    "\n===== CONTENUTO TOOLTIP ====="
                )

                print(
                    popup_text
                )

                print(
                    "\n=============================\n"
                )

                hostname = fw_name
                serial = ""
                management_ip = ""

                m = re.search(
                    r"Hostname\s+(.*?)\s+Serial Number",
                    popup_text,
                    re.IGNORECASE
                )

                if m:

                    hostname = (
                        m.group(1)
                        .strip()
                    )

                m = re.search(
                    r"Serial Number\s+([A-Z0-9]+)\s+Authorization Type",
                    popup_text,
                    re.IGNORECASE
                )

                if m:

                    serial = (
                        m.group(1)
                        .strip()
                    )

                m = re.search(
                    r"Management IP/FQDN\s*(\d+\.\d+\.\d+\.\d+)\s*Management Port",
                    popup_text,
                    re.IGNORECASE
                )

                if m:

                    management_ip = (
                        m.group(1)
                        .strip()
                    )

                print(
                    "\n===== DATI ESTRATTI ====="
                )

                print(
                    f"Hostname      : {hostname}"
                )

                print(
                    f"Serial Number : {serial}"
                )

                print(
                    f"Management IP : {management_ip}"
                )

                print(
                    "=========================\n"
                )

                results.append(
                    {
                        "adom": adom,
                        "area_vasta": area_vasta,
                        "fortimanager_ip": source_ip,
                        "fortimanager_hostname": fmgr_hostname,
                        "hostname": hostname,
                        "serial": serial,
                        "management_ip": management_ip
                    }
                )

                success = True

                break

            except (
                StaleElementReferenceException,
                TimeoutException,
                NoSuchElementException
            ) as e:

                print(
                    f"[WARN] Tentativo {retry + 1} fallito: {e}"
                )

                time.sleep(2)

            except Exception as e:

                print(
                    f"[WARN] Tentativo {retry + 1} fallito: {e}"
                )

                time.sleep(2)

        if not success:

            print(
                f"[ERROR] Impossibile processare {fw_name}"
            )

            failed_firewalls.append(
                {
                    "adom": adom,
                    "area_vasta": area_vasta,
                    "fortimanager_ip": source_ip,
                    "fortimanager_hostname": fmgr_hostname,
                    "hostname": fw_name,
                    "serial": "",
                    "management_ip": ""
                }
            )

    results.extend(
        failed_firewalls
    )

    print(
        "\n========================================"
    )

    print(
        "HOSTNAME ; SERIAL NUMBER ; MANAGEMENT IP"
    )

    print(
        "========================================"
    )

    for item in results:

        print(
            f"{item['hostname']} ; "
            f"{item['serial']} ; "
            f"{item['management_ip']}"
        )

    print(
        "\n========================================"
    )

    print(
        f"Firewall elaborati : {len(results)}"
    )

    print(
        f"Firewall riusciti  : {len(results) - len(failed_firewalls)}"
    )

    print(
        f"Firewall falliti   : {len(failed_firewalls)}"
    )

    if failed_firewalls:

        print(
            "\n===== FIREWALL FALLITI ====="
        )

        for item in failed_firewalls:

            print(
                item["hostname"]
            )

        print(
            "============================"
        )

    return results


def export_to_csv(results):

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"fortigate_inventory_{timestamp}.csv"
    )

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:

        writer = csv.writer(
            csvfile,
            delimiter=";"
        )

        writer.writerow(
            [
                "ADOM",
                "Area Vasta",
                "FortiManager IP",
                "FortiManager Hostname",
                "Hostname",
                "Serial Number",
                "Management IP"
            ]
        )

        for item in results:

            writer.writerow(
                [
                    item["adom"],
                    item["area_vasta"],
                    item["fortimanager_ip"],
                    item["fortimanager_hostname"],
                    item["hostname"],
                    item["serial"],
                    item["management_ip"]
                ]
            )

    print(
        f"\n[OK] CSV salvato: {filename}"
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    username = input(
        "\nUsername FortiManager: "
    )

    password = getpass(
        "Password FortiManager: "
    )
    all_results = []

    options = webdriver.EdgeOptions()

    options.add_argument(
        "--ignore-certificate-errors"
    )

    options.add_argument(
        "--ignore-ssl-errors"
    )

    options.add_argument(
        "--allow-insecure-localhost"
    )

    options.set_capability(
        "acceptInsecureCerts",
        True
    )

    driver = webdriver.Edge(
        options=options
    )

    driver.maximize_window()

    try:

        for (
            ip,
            port,
            adom,
            area_vasta,
            fmgr_hostname
        ) in FORTIMANAGERS:

            print(
                f"\n########## {adom} ##########"
            )
            login_fortimanager(
                driver,
                ip,
                port,
                username,
                password
            )
            open_firewall_dropdown(
                driver
            )

            current_results = dump_firewall_tooltips(
                driver,
                ip,
                adom,
                area_vasta,
                fmgr_hostname
            )

            all_results.extend(
                current_results
            )

        export_to_csv(
            all_results
        )
        print(
            "\nPremi INVIO per chiudere il browser..."
        )

        input()

    finally:

        driver.quit()


if __name__ == "__main__":
    main()