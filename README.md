## How to Run

1. Run the `initschema.py` script with `--user`, `--password` and `--host` arguments for the Postgres DB. Ex: `python3 initschema.py --user postgres --password password --host localhost`.
2. Run the `drugbank_scraper.py` file to transact values into the Postgres DB with `--user`, `--password` and `--host` arguments. Ex: `python3 drugbank_scraper.py --user postgres --password password --host localhost`.

## Schema Design

The schema for this engineering task was designed as three separate tables.

The first table is "drugs", where each row corresponds to a drug along with any uniquely identifying information about that drug. Right now, that only includes a SMILES string (which in an ideal world would be canonical and is assumed to be in the schema provided). The IDs of this table would provide the business specific IDs by which the drug would be universally referred to by within the organization.

The second table is "alternate_identifiers". Each row in this table lists a mapping between the internal ID provided by the "drugs" table and alternative IDs provided by other sources like Drugbank, or PubChem. This data is presented in this way since it's expected that not every drug would be universally present in all data sources.

The third table is "gene_actions". Each row in this table lists a mapping between the internal ID provided by the "drugs" table and a known gene target. Each row corresponds to a known gene target and a possible action. If the gene target is known but not the action of the drug, we record the gene name will a null value for the action.

## Ingestion Tool Design

A few high level principles that I like to apply to data ingestion and transformation processes:

- No data is better than bad data. This is especially important when we need to train reliable machine learning models.
- Fail fast and alert if data doesn't meet expectations. Validation and understanding of the data that's being ingested is important, and ensuring that we alert loudly, fail, and don't record data which doesn't meet assumptions because it may mean our model of the data is wrong or the data has changed.
- Establish a domain model of data and processes frequently used. This encourages designing code in a way that's highly readable, understandable, modular and reusable.

The overall design for data ingestion is that everything is a set of testable/deterministic black boxes. (A "functional programming"/stateless style approach.) Each stage of a data ingestion or transformation process should always produce the same output for the same input, and side effects like transacting to a database should be well controlled for and understood. Done well, this means that tasks can be handed out piecemeal because the input is well defined and the expected output is well defined, even if those pieces of the pipeline aren't created yet.

Tools like Apache Airflow lend themselves well to this approach. (If pursuing batch/scheduled work rather than streaming.) Then switching between managing "smaller" datasets and "larger" ones can be a matter of using the right operators, like a Spark or Hive operator instead of running a self-contained Python script.

Retrieval steps for an API or web scraping script are as self-contained as possible so that if the underlying shape changes it's easy enough to slot in an update. And by the fail fast principle, our code blocks which are performing the retrieval will fail rather than proceed as if nothing happened. And we would also use a suite of integration tests which are regularly run to proactively monitor for changes.

If API limits are a concern for some websites, the system should accomodate scaling out with machines with distinct IPs in order to stay within bounds and not end up with a banned or throttled agent.

## Future Enhancements

The provided code is very much an MVP example of a retrieval script. Here's a list of changes that are needed to better adhere to the described principles before.

1. Retrieval and database transaction should take place in different "places". In practice and budget allowing, I'd want to write out the results of a retrieval step to a staging area like an intermediate SQL table and/or long term storage area like S3. Then a separate step would pick up that data and put it into the datastore of choice. This staging area afford flexibility in swapping out the endpoint or parallelizing the ingestion of that data into multiple different stores. (Perhaps we wish to put some unstructured component of the retrieval in a NoSQL database and relationally modelled things in the SQL database.)
2. The code is going to be brittle if the underlying HTML shape changes at all. I prefer that overall because I WANT the code to break if the shape changes because I don't want to record bad data. But this code isn't going to provide enlightening log messages or guide posts about what changed and we'll likely only know the code stopped working. So we'd want more insightful messages placed in a logging service somewhere which is suggestive about what went work.
3. Related, if latency isn't a huge concern, putting a validation step in to ensure that the data retrieved matches expectations is valuable between retrieval and ingestion. Things like ensuring that the smiles string actually has "C"'s in it or that the gene name corresponds to some other table with known gene names.
4. I took a fairly naive approach to bulk inserting. There are probably much more efficient ways to do that when the data to be inserted is a larger amount.
