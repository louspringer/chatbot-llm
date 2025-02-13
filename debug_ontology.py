#!/usr/bin/env python3
from rdflib import Graph, Namespace, URIRef

g = Graph()
# Bind the namespace to prevent file:/// URIs
DEPLOY = Namespace("deployment#")
g.bind("deploy", DEPLOY)
g.parse("deployment.ttl", format="turtle")


def get_local_name(uri):
    """Extract local name from URIRef, handling both relative and absolute URIs."""
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[1]
    return uri_str.split("/")[-1]


print("Dependencies:")
for s, p, o in g.triples((None, DEPLOY.dependsOn, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nConfigurations:")
for s, p, o in g.triples((None, DEPLOY.configures, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nEmulations:")
for s, p, o in g.triples((None, DEPLOY.emulates, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nUsed In:")
for s, p, o in g.triples((None, DEPLOY.usedIn, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")

print("\nImplemented By:")
for s, p, o in g.triples((None, DEPLOY.implementedBy, None)):
    print(f"{get_local_name(s)} -> {get_local_name(o)}")
