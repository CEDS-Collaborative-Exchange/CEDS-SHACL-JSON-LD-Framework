#!/usr/bin/env python3
"""
CEDS Property Shapes Generator - Updated Version

This script parses the CEDS Ontology RDF file and generates/updates 
PropertyShapes-Terms.ttl with SHACL property shapes for all data properties.

Updated to work with actual CEDS ontology structure.
"""

import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS
import re
from collections import defaultdict, OrderedDict
from pathlib import Path

# Define namespaces
CEDS = Namespace("http://ceds.ed.gov/terms#")
SCHEMA = Namespace("https://schema.org/")
SH = Namespace("http://www.w3.org/ns/shacl#")


class CEDSPropertyShapesGenerator:
    def __init__(self, ontology_path, shapes_path):
        self.ontology_path = Path(ontology_path)
        self.shapes_path = Path(shapes_path)
        
        # Load ontology
        print(f"Loading ontology from {ontology_path}...")
        self.ontology_graph = Graph()
        self.ontology_graph.parse(str(self.ontology_path), format="xml")
        print(f"Loaded {len(self.ontology_graph)} triples from ontology")
        
        # Bind namespaces
        self.ontology_graph.bind("ceds", CEDS)
        self.ontology_graph.bind("schema", SCHEMA)
        self.ontology_graph.bind("sh", SH)
        self.ontology_graph.bind("xsd", XSD)
        self.ontology_graph.bind("skos", SKOS)
        
        self.data_properties = {}
        self.enumeration_classes = {}
        self.property_enum_mapping = {}  # Map properties to their enumeration classes
        
    def extract_enumeration_classes(self):
        """Extract all C0* enumeration classes and their named individuals"""
        print("Extracting enumeration classes...")
        
        enum_classes = []
        for cls in self.ontology_graph.subjects(RDF.type, OWL.Class):
            cls_str = str(cls)
            enum_classes.append(cls)
        
        print(f"Found {len(enum_classes)} enumeration classes")
        
        for i, enum_class in enumerate(enum_classes):
            if i % 100 == 0:
                print(f"Processing enumeration class {i+1}/{len(enum_classes)}")
                
            # Find all named individuals for this enumeration class
            individuals = []
            for individual in self.ontology_graph.subjects(SKOS.inScheme, enum_class):
                if self.ontology_graph.value(individual, RDF.type) == OWL.NamedIndividual:
                    # Get the label for comment
                    label = self._get_annotation(individual, RDFS.label)
                    individuals.append({
                        'uri': individual,
                        'label': label or str(individual).split('#')[-1]
                    })
            
            if individuals:
                self.enumeration_classes[enum_class] = sorted(individuals, key=lambda x: str(x['uri']))
        
        print(f"Processed {len(self.enumeration_classes)} enumeration classes with individuals")
    
    def build_property_enum_mapping(self):
        """Build mapping from property names to enumeration classes"""
        print("Building property to enumeration mapping...")
        
        # This is based on naming convention analysis
        # Properties that start with "has" + enumeration class name tend to point to that class
        for enum_class in self.enumeration_classes.keys():
            class_name = str(enum_class)  # e.g., "C000255" 
            
            # Look for properties that might map to this enumeration
            # This is heuristic-based since the ontology doesn't have explicit range declarations
            for prop in self.ontology_graph.subjects(SCHEMA.rangeIncludes, URIRef(class_name)):
                self.property_enum_mapping[str(prop)] = enum_class
        
        print(f"Mapped {len(self.property_enum_mapping)} properties to enumeration classes")
    
    def extract_data_properties(self):
        """Extract all P* data properties"""
        print("Extracting data properties...")
        
        all_props = []
        for prop, _, range_obj in self.ontology_graph.triples((None, SCHEMA.rangeIncludes, None)):
            if str(range_obj).startswith(str(XSD)) or self.enumeration_classes.get(URIRef(str(range_obj))):
                all_props.append(prop)
        
        print(f"Found {len(all_props)} P* properties")
        
        for i, prop in enumerate(all_props):
            if i % 500 == 0:
                print(f"Processing property {i+1}/{len(all_props)}")
            
            # Extract property metadata
            prop_data = {
                'uri': prop,
                'name': self._get_property_name(prop),
                'notation': self._get_annotation(prop, SKOS.notation),
                'enumeration_class': self.property_enum_mapping.get(str(prop)),
                'datatype':  self._get_annotation(prop, SCHEMA.rangeIncludes),
                'max_length': self._get_annotation(prop, CEDS.maxLength),
                'min_length': self._get_annotation(prop, CEDS.minLength),
                'text_format': self._get_annotation(prop, CEDS.textFormat),
                'decimal_places': self._get_annotation(prop, CEDS.decimalPlaces),
            }
            
            self.data_properties[prop] = prop_data
        
        print(f"Processed {len(self.data_properties)} data properties")
    
    
    def _get_property_name(self, prop):
        """Extract readable name for property"""
        # Try schema:name first
        name = self._get_annotation(prop, SCHEMA.name)
        if name:
            return name
        
        # Try rdfs:label
        name = self._get_annotation(prop, RDFS.label)
        if name:
            return name
        
        # Fallback to URI fragment
        return str(prop).split('#')[-1]
    
    def _get_annotation(self, subject, predicate):
        """Get annotation value as string"""
        value = self.ontology_graph.value(subject, predicate)
        if value:
            if isinstance(value, Literal):
                return str(value)
            else:
                return str(value)
        return None
    
    def write_property_shapes_ttl(self, output_path=None):
        """Write property shapes to TTL file"""
        if output_path is None:
            output_path = self.shapes_path
        
        print(f"Writing property shapes to {output_path}...")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("@prefix sh: <http://www.w3.org/ns/shacl#> .\n")
            f.write("@prefix ceds: <http://ceds.ed.gov/terms#> .\n")
            f.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> . \n\n")
            
            # Sort properties by ID for consistent output
            sorted_props = sorted(self.data_properties.items(), key=lambda x: str(x[0]))
            
            for prop, prop_data in sorted_props:
                prop_id = str(prop).split('#')[-1]
                
                # Write the shape
                f.write(f"ceds:{prop_data['notation']}Shape\n")
                f.write(f"  a sh:PropertyShape ;\n")
                f.write(f"  sh:path ceds:{prop_id} ;\n")
                f.write(f"  sh:name \"{prop_data['name']}\"")
                
                # Handle enumeration properties
                if prop_data['enumeration_class']:
                    enum_class = prop_data['enumeration_class']
                    if enum_class in self.enumeration_classes:
                        f.write(" ;\n")
                        f.write(f"  sh:nodeKind sh:IRI ;\n")
                        individuals = self.enumeration_classes[enum_class]
                        if individuals:
                            f.write(f"  sh:in (\n")
                            for individual in individuals:
                                individual_id = str(individual['uri']).split('#')[-1]
                                comment = f"    # {individual['label']}" if individual['label'] != individual_id else ""
                                f.write(f"    ceds:{individual_id}{comment}\n")
                            f.write(f"  )")
                
                # Handle basic datatype properties
                elif prop_data['datatype']:
                    datatype_name = str(prop_data['datatype']).split('#')[-1]
                    f.write(" ;\n")
                    f.write(f"  sh:datatype xsd:{datatype_name}")
                    
                    # Add constraints
                    if prop_data['max_length']:
                        try:
                            max_len = int(prop_data['max_length'])
                            f.write(" ;\n")
                            f.write(f"  sh:maxLength {max_len}")
                        except (ValueError, TypeError):
                            pass
                    
                    if prop_data['min_length']:
                        try:
                            min_len = int(prop_data['min_length'])
                            f.write(" ;\n")
                            f.write(f"  sh:minLength {min_len}")
                        except (ValueError, TypeError):
                            pass
                    
                    if prop_data['text_format']:
                        text_format = prop_data['text_format']
                        if text_format.startswith('^') and text_format.endswith('$'):
                            # Escape backslashes for TTL
                            escaped_pattern = text_format.replace('\\\\', '\\\\\\\\')
                            f.write(" ;\n")
                            f.write(f"  sh:pattern \"{escaped_pattern}\"")
                    
                    if prop_data['decimal_places']:
                        try:
                            decimal_places = int(prop_data['decimal_places'])
                            f.write(" ;\n")
                            f.write(f"  sh:fractionDigits {decimal_places}")
                        except (ValueError, TypeError):
                            pass
                
                f.write(" ;\n")
                f.write(".\n\n")
        
        print(f"Successfully wrote property shapes to {output_path}")
    
    def run(self):
        """Main execution method"""
        print("Starting CEDS Property Shapes Generator...")
        
        # Extract data from ontology
        self.extract_enumeration_classes()
        self.build_property_enum_mapping()
        self.extract_data_properties()
        
        # Generate new shapes file
        self.write_property_shapes_ttl()
        
        print("Property shapes generation completed!")
        
        # Print summary
        print("\n=== SUMMARY ===")
        print(f"Data properties processed: {len(self.data_properties)}")
        print(f"Enumeration classes found: {len(self.enumeration_classes)}")
        print(f"Properties mapped to enumerations: {len([p for p in self.data_properties.values() if p['enumeration_class']])}")

def main():
    ontology_path = r"C:\Repos\CEDS-Ontology\src\CEDS-Ontology.rdf"
    shapes_path = r"C:\Repos\CEDS-JSON-JSON-LD-Framework\src\PropertyShapes-Terms-Generated.ttl"
    
    generator = CEDSPropertyShapesGenerator(ontology_path, shapes_path)
    generator.run()

if __name__ == "__main__":
    main()