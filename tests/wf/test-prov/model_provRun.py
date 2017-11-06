
# -*- coding: utf-8 -*-
from prov.model import ProvDocument
import io
from prov.dot import prov_to_dot
import pydot
import uuid
#prov_doc=open("prov_doc.txt", "w")
d1=ProvDocument()
# Declaring namespaces for various prefixes used in the example
d1.add_namespace('now', 'http://www.provbook.org/nownews/')
d1.add_namespace('nowpeople', 'http://www.provbook.org/nownews/people/')
d1.add_namespace('wfprov', 'http://wf4ever.github.io/ro/#wfprov')
d1.add_namespace('bk', 'http://www.provbook.org/ns/#')

# Entity: now:employment-article-v1.html
e1 = d1.entity('now:employment-article-v1.html')
# Agent: nowpeople:Bob
d1.agent('nowpeople:Bob')

# Attributing the article to the agent
d1.wasAttributedTo(e1, 'nowpeople:Bob')

#add more namespaces
d1.add_namespace("govftp", "ftp://ftp.bls.gov/pub/special.requests/oes/")
d1.add_namespace("void", "http://vocab.deri.ie/void#")

# 'now:employment-article-v1.html' was derived from at dataset at govftp
d1.entity('govftp:oesmlist.zip', {"prov:label":"employment-stats-2011", 'prov:type': "void:Dataset"})
d1.wasDerivedFrom("now:employment-article-v1.html", "govftp:oeamlist.zip")

# Adding an activity
d1.add_namespace('is', 'http://www.provbook.org/nownews/is/#')
d1.activity('is:writeArticle')

# Usage and Generation
d1.used('is:writeArticle', 'govftp:oesm11st.zip')
d1.wasGeneratedBy('now:employment-article-v1.html', 'is:writeArticle')

dot=prov_to_dot(d1)

dot.write_png('article-prov.png')
d1.serialize('article-prov.json', indent=2)
#prov_doc.write(d1.get_provn())
#prov_doc.close()
#print(d1.get_provn())
