import requests
from bs4 import BeautifulSoup
import psycopg2
import argparse


def get_smiles(parsed_drug_doc):
    """
    Retrieve the SMILES string describing the drug in the parsed HTML document.

    We get the SMILES string by locating the HTML id "smiles" and then moving to the
    next html element. This process is slightly complicated by the fact that the SMILES string
    is confused for an email due to the presence of @ characters, and so we have to decode the
    email obfuscation used.

    NOTE: I was unable to determine if the SMILES string provided is canonical/unique.
          It would be nice to have that to provide disambiguation in the database.
          (https://en.wikipedia.org/wiki/Simplified_molecular-input_line-entry_system#Terminology)
    """

    # Source: https://stackoverflow.com/questions/36911296/scraping-of-protected-email
    def decode_email(e):
        de = ""
        k = int(e[:2], 16)

        for i in range(2, len(e)-1, 2):
            de += chr(int(e[i:i+2], 16)^k)

        return de

    email_protected_map = {}
    for email_protected in parsed_drug_doc.find_all(class_="__cf_email__"):
        email_protected_map[str(email_protected)] = decode_email(email_protected["data-cfemail"])

    unencrypted_string = str(parsed_drug_doc.find(id="smiles").next_sibling)
    for href, unencrypted in email_protected_map.items():
        unencrypted_string = unencrypted_string.replace(href, unencrypted)

    smile_result = BeautifulSoup(unencrypted_string, 'html.parser').text

    if smile_result == "Not Available":
        smile_result = None

    return smile_result


def get_gene_action_pairs(parsed_drug_doc):
    """
    Retrieve the targets gene names and actions.

    For the drugs with targets, we can find the section using the id "targets".
    Those targets may have a gene name listed or not.
    If the target has a gene name listed, it may have zero or many actions associated.
    """

    gene_action_pairs = []
    for target in parsed_drug_doc.select('#targets .card-body'):
        # We may have zero or one gene names.
        gene_name_section = target.find(id='gene-name')
        if gene_name_section:
            gene_name = gene_name_section.next_sibling.text

            actions_section = target.find(id='actions')

            # We may be missing actions but have gene name.
            if not actions_section:
                gene_action_pairs.append((gene_name, None))
            else:
                # We may have multiple actions.
                actions = actions_section.next_sibling.find_all(class_="badge")
                for action in actions:
                    gene_action_pairs.append((gene_name, action.text))
        else:
            # Skip recording information if we don't have a gene name.
            pass

    return gene_action_pairs


def get_external_links(parsed_drug_doc):
    """
    Retrieves the alternative identifiers for other drug info sources.

    Finds the section using the id "external-links".
    """

    external_link_info = list(parsed_drug_doc.find(id='external-links').next_sibling.dl.children)
    external_links = {}
    for i in range(0, len(external_link_info), 2):
        source = external_link_info[i].text
        value = external_link_info[i+1].text
        # Ignoring a few sources for this MVP that don't give obvious alternate IDs.
        if source not in ["RxList", "Drugs.com", "PDRhealth"]:
            external_links[source] = value

    return external_links


def get_info_for_identifier(identifier):
    """
    Retrieves a set of information for a given Drugbank drug identifier.
    """

    page = requests.get(f"https://www.drugbank.ca/drugs/{identifier}")
    parsed_drug_doc = BeautifulSoup(page.text, 'html.parser')

    smiles = get_smiles(parsed_drug_doc)
    gene_action_pairs = get_gene_action_pairs(parsed_drug_doc)
    external_links = get_external_links(parsed_drug_doc)

    # print("identifier", identifier)
    # print("smiles", smiles)
    # print("gene actions", gene_action_pairs)
    # print("external links", external_links)

    return {
        "identifier": identifier,
        "smiles": smiles,
        "gene_action_pairs": gene_action_pairs,
        "external_links": external_links
    }


def get_postgres_conn_and_cursor(user, password, host):
    """
    Returns a psycopg2 connection and cursor for performing SQL operations.
    """

    conn = psycopg2.connect(user=user, password=password, host=host, connect_timeout=10)
    cursor = conn.cursor()

    return conn, cursor


def transact_drug_info(identifiers, user, password, host):
    """
    Retrieves the info from Drugbank for the provided identifiers,
    prepares insert statements for the info and then performs them.

    NOTE: Will fail if the data is already present.
    """

    drug_info = []
    for identifier in identifiers:
        drug_info.append(get_info_for_identifier(identifier))

    def xform_for_insert(t):
        return str(t).replace('"', "'").replace("None", "NULL")

    drugs_txs = []
    gene_action_pairs_txs = []
    alternate_identifiers_txs = []
    for i, drug_info in enumerate(drug_info):
        drugs_txs.append(
            xform_for_insert((i, drug_info["smiles"]))
        )

        gene_action_pairs = drug_info["gene_action_pairs"]
        for pair in gene_action_pairs:
            gene_action_pairs_txs.append(
                xform_for_insert((i, pair[0], pair[1]))
            )

        external_links = drug_info["external_links"]
        for identifier_source, identifier_value in external_links.items():
            alternate_identifiers_txs.append(
                xform_for_insert((i, identifier_source, identifier_value))
            )

    drugs_insert = f"""INSERT INTO drug_info.drugs
                        (drug_id, smiles) VALUES
                        {', '.join(drugs_txs)};
                    """

    alt_ids_insert = f"""INSERT INTO drug_info.alternate_identifiers
                        (drug_id, identifier_source, identifier_value) VALUES
                        {', '.join(alternate_identifiers_txs)};
                    """

    gene_actions_insert = f"""INSERT INTO drug_info.gene_actions
                                (drug_id, gene_name, gene_action) VALUES
                                {', '.join(gene_action_pairs_txs)};
                            """

    conn, cursor = get_postgres_conn_and_cursor(user, password, host)

    cursor.execute(drugs_insert)
    cursor.execute(alt_ids_insert)
    cursor.execute(gene_actions_insert)

    # cursor.execute("SELECT * FROM drug_info.drugs")
    # print(cursor.fetchall())
    # cursor.execute("SELECT * FROM drug_info.alternate_identifiers")
    # print(cursor.fetchall())
    # cursor.execute("SELECT * FROM drug_info.gene_actions")
    # print(cursor.fetchall())

    conn.commit()

    cursor.close()
    conn.close()

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', default='postgres')
    parser.add_argument('--password', default='password')
    parser.add_argument('--host', default='localhost')

    args = parser.parse_args()

    user = args.user
    password = args.password
    host = args.host

    identifiers = [
        "DB00006", "DB00619", "DB01048", "DB14093",
        "DB00173", "DB00734", "DB00218", "DB05196",
        "DB09095", "DB01053", "DB00274"
    ]

    transact_drug_info(identifiers, user, password, host)
