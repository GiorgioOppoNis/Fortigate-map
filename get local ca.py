from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import csv
import time
import os


# =====================================================
# CONFIGURAZIONE
# =====================================================

FORTIGATES = [
("10.211.0.1",10443),
("10.211.0.2",10443),
("10.211.0.3",10444),
("10.211.0.4",10443),
("10.211.0.5",10443),
("10.211.0.6",10443),
("10.211.0.7",10443),
("10.211.0.8",10443),
("10.211.0.9",10443),
("10.211.0.10",10443),
("10.211.0.11",10443),
("10.211.0.12",10443),
("10.211.0.13",10443),
("10.211.0.14",10444),
("10.211.0.15",10443),
("10.211.0.16",10443),
("10.211.0.18",10443),
("10.211.0.19",10443),
("10.211.0.20",10443),
#("10.211.0.21",10444),
("10.211.0.22",10443),
("10.211.0.23",10443),
("10.211.0.24",10443),
("10.211.0.25",10443),
("10.211.0.26",10443),
]

OUTPUT_FILE = "local_certificates.csv"


# =====================================================
# UTILITY
# =====================================================

def safe_click(driver, element):
    try:
        element.click()
    except Exception:
        driver.execute_script(
            "arguments[0].click();",
            element
        )


def extract_cn(value):

    if not value:
        return value

    for part in value.split(","):

        part = part.strip()

        if part.startswith("CN = "):
            return part.replace("CN = ", "").strip()

    return value


# =====================================================
# LOGIN
# =====================================================

def login(driver, wait, base_url):

    print(f"\nLogin su {base_url}")

    driver.get(f"{base_url}/login")

    wait.until(
        lambda d: "/login" not in d.current_url
    )

    print("Login completato")

    time.sleep(3)


# =====================================================
# MENU VDOM
# =====================================================

def open_vdom_menu(driver, wait):

    button = wait.until(
        EC.element_to_be_clickable(
            (
                By.CSS_SELECTOR,
                "button.pop-up-menu-hover-toggle-attached"
            )
        )
    )

    safe_click(driver, button)

    time.sleep(2)


# =====================================================
# RECUPERO VDOM
# =====================================================

def get_vdoms(driver):

    vdoms = []

    entries = driver.find_elements(
        By.XPATH,
        """
        //nu-menu-item-button[
            .//nu-icon[
                contains(@data-nu-icon,'vdom')
            ]
        ]
        """
    )

    for entry in entries:

        try:

            name = (
                entry.find_element(
                    By.CSS_SELECTOR,
                    "span.name"
                )
                .text
                .strip()
            )

            if (
                name
                and name not in vdoms
            ):
                vdoms.append(name)

        except Exception:
            pass

    return vdoms


# =====================================================
# APERTURA PAGINA CERTIFICATI
# =====================================================

def open_vdom_certificates(
    driver,
    wait,
    base_url,
    vdom
):

    url = (
        f"{base_url}/ng/system/certificate"
        f"?vdom={vdom}"
    )

    print(f"Apro {url}")

    driver.get(url)

    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//*[@section-id='Local Certificate']"
            )
        )
    )

    time.sleep(2)


# =====================================================
# ESTRAZIONE CERTIFICATI
# =====================================================

def extract_certificates(
    driver,
    fortigate,
    vdom
):

    rows = driver.find_elements(
        By.XPATH,
        """
        //*[
            contains(@class,'row')
            and contains(@class,'selectable')
            and contains(@class,'reorderable-row')
            and preceding::*[@section-id='Local Certificate']
            and following::*[@section-id='Remote CA Certificate']
        ]
        """
    )

    print(
        f"{fortigate} | {vdom} -> {len(rows)} righe"
    )

    if not rows:
        return None, []

    headers = [
        "fortigate",
        "vdom"
    ]

    first_cells = rows[0].find_elements(
        By.CSS_SELECTOR,
        "[column-id]"
    )

    for cell in first_cells:

        column_id = cell.get_attribute(
            "column-id"
        )

        if column_id:
            headers.append(column_id)

    records = []

    for row in rows:

        record = [
            fortigate,
            vdom
        ]

        cells = row.find_elements(
            By.CSS_SELECTOR,
            "[column-id]"
        )

        for index, cell in enumerate(cells):

            value = (
                cell.text
                .replace("\n", " ")
                .replace(";", ",")
                .strip()
            )

            if index == 1:
                value = extract_cn(value)

            record.append(value)

        if len(record) > 2:
            records.append(record)

    return headers, records


# =====================================================
# PROCESSA FORTIGATE
# =====================================================

def process_fortigate(
    driver,
    wait,
    host,
    port
):

    base_url = f"https://{host}:{port}"

    login(
        driver,
        wait,
        base_url
    )

    open_vdom_menu(
        driver,
        wait
    )

    vdoms = get_vdoms(driver)

    print(
        f"\n{host}:{port} - VDOM trovati:"
    )

    for v in vdoms:
        print(f"  - {v}")

    headers = None
    all_records = []

    for vdom in vdoms:

        try:

            print(
                f"\nElaborazione {host}:{port} -> {vdom}"
            )

            open_vdom_certificates(
                driver,
                wait,
                base_url,
                vdom
            )

            current_headers, records = (
                extract_certificates(
                    driver,
                    f"{host}:{port}",
                    vdom
                )
            )

            if (
                current_headers
                and headers is None
            ):
                headers = current_headers

            all_records.extend(records)

        except Exception as ex:

            print(
                f"Errore su {host}:{port} - {vdom}"
            )

            print(ex)

    return headers, all_records


# =====================================================
# CSV
# =====================================================

def save_csv(
    filename,
    headers,
    records
):

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.writer(
            f,
            delimiter=";"
        )

        if headers:
            writer.writerow(headers)

        writer.writerows(records)


# =====================================================
# MAIN
# =====================================================

def main():

    options = webdriver.ChromeOptions()

    options.add_argument(
        "--ignore-certificate-errors"
    )

    options.add_argument(
        "--start-maximized"
    )

    driver = webdriver.Chrome(
        options=options
    )

    wait = WebDriverWait(
        driver,
        300
    )

    csv_headers = None
    csv_records = []

    try:

        for host, port in FORTIGATES:

            headers, records = (
                process_fortigate(
                    driver,
                    wait,
                    host,
                    port
                )
            )

            if (
                headers
                and csv_headers is None
            ):
                csv_headers = headers

            csv_records.extend(records)

        output_file = os.path.join(
            os.getcwd(),
            OUTPUT_FILE
        )

        save_csv(
            output_file,
            csv_headers,
            csv_records
        )

        print("\n================================")
        print("CSV CREATO")
        print(output_file)
        print(
            f"Totale record: {len(csv_records)}"
        )
        print("================================")

    finally:

        input(
            "\nPremi INVIO per chiudere..."
        )

        driver.quit()


if __name__ == "__main__":
    main()