import argparse
import psycopg2

# docker run --rm -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', default='postgres')
    parser.add_argument('--password', default='password')
    parser.add_argument('--host', default='localhost')

    args = parser.parse_args()

    user = args.user
    password = args.password
    host = args.host

    conn = psycopg2.connect(user=user, password=password, host=host, connect_timeout=10)
    cursor = conn.cursor()

    response = cursor.execute("""CREATE SCHEMA drug_info;""")

    response = cursor.execute("""CREATE TABLE drug_info.drugs (
                        drug_id integer PRIMARY KEY,
                        smiles text UNIQUE
                      );
                   """)

    response = cursor.execute("""CREATE TABLE drug_info.alternate_identifiers (
                        link_id SERIAL PRIMARY KEY,
                        drug_id integer,
                        CONSTRAINT drug_id FOREIGN KEY(drug_id) REFERENCES drug_info.drugs(drug_id),
                        identifier_source text,
                        identifier_value text,
                        UNIQUE(identifier_source, identifier_value)
                      );
                   """)

    response = cursor.execute("""CREATE TABLE drug_info.gene_actions (
                        action_id SERIAL PRIMARY KEY,
                        drug_id integer,
                        CONSTRAINT drug_id FOREIGN KEY(drug_id) REFERENCES drug_info.drugs(drug_id),
                        gene_name text,
                        gene_action text,
                        UNIQUE(gene_name, gene_action)
                      );
                   """)

    conn.commit()

    cursor.close()
    conn.close()