import pytest
from pathlib import Path
from app.ingestion.xml_parser import MedlinePlusXMLParser, MedlineTopicRecord

def test_xml_parser_valid_file(tmp_path):
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <health-topics total="1">
        <health-topic id="mplus-test" title="Test Hypertension" url="https://medlineplus.gov/test.html" date-created="2023-11-10">
            <full-summary>Hypertension is high blood pressure exceeding 130/80 mmHg.</full-summary>
            <keyword>blood pressure</keyword>
            <keyword>hypertension</keyword>
            <mesh-heading>Hypertension</mesh-heading>
        </health-topic>
    </health-topics>
    """
    xml_file = tmp_path / "test_topics.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    topics = MedlinePlusXMLParser.parse_xml_file(xml_file)
    assert len(topics) == 1
    assert topics[0].title == "Test Hypertension"
    assert "130/80" in topics[0].summary
    assert "blood pressure" in topics[0].keywords
    assert topics[0].authority_tier == 1

def test_xml_parser_lenient_regex_fallback(tmp_path):
    # Malformed XML (unclosed tags)
    malformed_content = """<health-topics>
        <health-topic id="mplus-bad" title="Malformed Topic">
            <full-summary>This summary is extracted despite broken XML syntax.
        </health-topic>
    """
    xml_file = tmp_path / "broken.xml"
    xml_file.write_text(malformed_content, encoding="utf-8")

    topics = MedlinePlusXMLParser.parse_xml_file(xml_file)
    assert len(topics) >= 1
    assert topics[0].title == "Malformed Topic"

def test_xml_parser_nonexistent():
    topics = MedlinePlusXMLParser.parse_xml_file("nonexistent.xml")
    assert topics == []
