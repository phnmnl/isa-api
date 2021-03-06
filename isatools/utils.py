def format_report_csv(report):
    """Format JSON validation report as CSV string

    :param report: JSON report output from validator
    :return: string representing csv formatted report
    """
    output = str()
    if report['validation_finished']:
        output = "Validation=success\n"
    for warning in report['warnings']:
        output += str("{},{},{}\n").format(warning['code'], warning['message'], warning['supplemental'])
    for error in report['errors']:
        output += str("{},{},{}\n").format(error['code'], error['message'], error['supplemental'])
    return output


def detect_graph_process_pooling(G):
    from isatools.model.v1 import Process
    report = list()
    for process in [n for n in G.nodes() if isinstance(n, Process)]:
        if len(G.in_edges(process)) > 1:
            print("Possible process pooling detected on: ", process.id)
            report.append(process.id)
    return report


def detect_isatab_process_pooling(tab_path):
    from isatools.convert import isatab2json
    from isatools import isajson
    from io import StringIO
    import json
    report = list()
    J = isatab2json.convert(tab_path, validate_first=False, use_new_parser=True)
    ISA = isajson.load(StringIO(json.dumps(J)))
    for study in ISA.studies:
        print("Checking {}".format(study.filename))
        pooling_list = detect_graph_process_pooling(study.graph)
        if len(pooling_list) > 0:
            report.append({
                study.filename: pooling_list
            })
        for assay in study.assays:
            print("Checking {}".format(assay.filename))
            pooling_list = detect_graph_process_pooling(assay.graph)
            if len(pooling_list) > 0:
                report.append({
                    assay.filename: pooling_list
                })
    return report


def insert_distinct_parameter(table_fp, protocol_ref_to_unpool):
    from isatools.isatab import load_table
    import uuid
    import csv
    reader = csv.reader(table_fp, dialect="excel-tab")
    headers = next(reader)  # get column headings
    table_fp.seek(0)
    df = load_table(table_fp)
    protocol_ref_indices = [x for x, y in enumerate(df.columns) if df[y][0] == protocol_ref_to_unpool]  # find protocol ref column by index
    if len(protocol_ref_indices) != 1:
        raise IndexError("Could not find Protocol REF with provided value {}".format(protocol_ref_to_unpool))
    distindex = list()
    for i in range(0, len(df.index)):
        distindex.append(str(uuid.uuid4())[:8])
    protocol_ref_index = protocol_ref_indices[0]
    name_header = None
    head_from_prot = headers[protocol_ref_index:]
    for x, y in enumerate(head_from_prot):
        if y.endswith(" Name"):
            name_header = y
            break
    if name_header is not None:
        print("Are you sure you want to add a column of hash values in {}? Y/(N)".format(name_header))
        confirm = input()
        if confirm == "Y":
            df[name_header] = distindex
            table_fp.seek(0)
            df.to_csv(table_fp, index=None, header=headers, sep='\t')
    else:
        print("Could not find appropriate column to fill with hashes")
    # return df


def contains(small_list, big_list):
    if len(small_list) == 0:
        return False
    for i in iter(range(len(big_list) - len(small_list) + 1)):
        for j in iter(range(len(small_list))):
            if big_list[i + j] != small_list[j]:
                break
        else:
            return i, i + len(small_list)
    return False


def get_pubmed_article(pubmed_id):
    # http://biopython.org/DIST/docs/tutorial/Tutorial.html#htoc126
    from Bio import Entrez, Medline
    response = {}
    Entrez.email = 'isatools@googlegroups.com'
    handle = Entrez.efetch(db="pubmed", id=pubmed_id.strip(), rettype="medline", retmode="text")
    records = Medline.parse(handle)
    for record in records:
        response['pubmedid'] = pubmed_id
        response['title'] = record.get("TI", "")
        response['authors'] = record.get("AU", "")
        response['journal'] = record.get("TA", "")
        response['year'] = record.get("EDAT", "").split('/')[0]
        lidstring = record.get("LID", "")
        if '[doi]' in lidstring:
            response['doi'] = record.get("LID", "").split(' ')[0]
        else:
            response['doi'] = ''
        if not response['doi']:
            aids = record.get("AID", "")
            for aid in aids:
                print("AID:" + aid)
                if '[doi]' in aid:
                    response['doi'] = aid.split(' ')[0]
                    break
                else:
                    response['doi'] = ''

        break
    return response


def set_pubmed_article(publication):
    """
        Given a Publication object with pubmed_id set to some value, set the rest of the values from information
        collected via Entrez webservice from PubMed
    """
    from isatools.model.v1 import Publication, Comment
    if isinstance(publication, Publication):
        response = get_pubmed_article(publication.pubmed_id)
        publication.doi = response['doi']
        publication.author_list = ", ".join(response['authors'])
        publication.title = response['title']
        publication.comments = [Comment(name='Journal', value=response['journal'])]
    else:
        raise TypeError("Can only set PubMed details on a Publication object")
