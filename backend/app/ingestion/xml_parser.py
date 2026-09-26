import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from app.utils.logger import logger
from app.utils.cache import cache

class MedlineTopicRecord:
    def __init__(
        self,
        topic_id: str,
        title: str,
        summary: str,
        url: str = "",
        date_created: str = "",
        keywords: Optional[List[str]] = None,
        mesh_headings: Optional[List[str]] = None,
        sections: Optional[List[Dict[str, str]]] = None,
        source_type: str = "authoritative_health_reference",
        publisher: str = "U.S. National Library of Medicine",
        authority_tier: int = 1
    ):
        self.topic_id = topic_id
        self.title = title
        self.summary = summary
        self.url = url or f"https://medlineplus.gov/{topic_id.lower()}.html"
        self.date_created = date_created or "2024-01-01"
        self.keywords = keywords or []
        self.mesh_headings = mesh_headings or []
        self.sections = sections or []
        self.source_type = source_type
        self.publisher = publisher
        self.authority_tier = authority_tier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "date_created": self.date_created,
            "keywords": self.keywords,
            "mesh_headings": self.mesh_headings,
            "sections": self.sections,
            "source_type": self.source_type,
            "publisher": self.publisher,
            "authority_tier": self.authority_tier
        }

class MedlinePlusXMLParser:
    """
    Resilient XML parser for MedlinePlus Health Topics.
    Supports official NLM bulk health-topic XMLs, single topic records, and synthetic fixtures.
    """

    @staticmethod
    def parse_xml_file(file_path: Union[str, Path]) -> List[MedlineTopicRecord]:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"MedlinePlus XML file not found at {path}. Returning empty list.")
            return []

        # Check cache based on file size and mtime
        stat = path.stat()
        cache_key = {"path": str(path), "mtime": stat.st_mtime, "size": stat.st_size}
        cached_data = cache.get("medlineplus_xml", cache_key)
        if cached_data:
            logger.info(f"Loaded {len(cached_data)} MedlinePlus topics from cache.")
            return [MedlineTopicRecord(**item) for item in cached_data]

        try:
            tree = ET.parse(str(path))
            root = tree.getroot()
        except ET.ParseError as e:
            logger.error(f"XML Parse error in {path}: {str(e)}. Attempting lenient regex extraction...")
            return MedlinePlusXMLParser._lenient_regex_parse(path)

        topics = []
        # Support various XML structures: <health-topics>, <topics>, or direct <health-topic>
        topic_nodes = root.findall(".//health-topic") or root.findall(".//topic")
        if not topic_nodes and root.tag in ("health-topic", "topic"):
            topic_nodes = [root]

        for idx, node in enumerate(topic_nodes):
            topic = MedlinePlusXMLParser._parse_topic_node(node, idx)
            if topic:
                topics.append(topic)

        logger.info(f"Successfully parsed {len(topics)} MedlinePlus topics from {path.name}")
        # Save to cache
        cache.set("medlineplus_xml", cache_key, [t.to_dict() for t in topics])
        return topics

    @staticmethod
    def _parse_topic_node(node: ET.Element, idx: int) -> Optional[MedlineTopicRecord]:
        topic_id = node.attrib.get("id") or node.attrib.get("topic-id") or f"MP-{idx+1:04d}"
        title = node.attrib.get("title") or ""
        
        # Check child tags for title if not in attributes
        if not title:
            title_tag = node.find("title") or node.find("name")
            if title_tag is not None and title_tag.text:
                title = title_tag.text.strip()
                
        url = node.attrib.get("url") or ""
        date_created = node.attrib.get("date-created") or ""

        # Summary
        summary = ""
        summary_elem = node.find("full-summary")
        if summary_elem is None:
            summary_elem = node.find("summary")
        if summary_elem is None:
            summary_elem = node.find("description")
            
        if summary_elem is not None:
            # Strip internal HTML tags if present (e.g. <b>, <a>, <p>)
            raw_summary = ET.tostring(summary_elem, encoding="unicode", method="text")
            summary = re.sub(r'\s+', ' ', raw_summary).strip()

        # Keywords / MeSH
        keywords = []
        for kw_tag in (node.findall(".//keyword") + node.findall(".//also-called")):
            if kw_tag.text and kw_tag.text.strip():
                keywords.append(kw_tag.text.strip())

        mesh_headings = []
        for mesh_tag in (node.findall(".//mesh-heading") + node.findall(".//descriptor")):
            if mesh_tag.text and mesh_tag.text.strip():
                mesh_headings.append(mesh_tag.text.strip())

        # Subsections
        sections = []
        for sec_tag in (node.findall(".//section") + node.findall(".//group")):
            sec_title = sec_tag.attrib.get("title") or sec_tag.findtext("title") or "General"
            sec_text = re.sub(r'\s+', ' ', ET.tostring(sec_tag, encoding="unicode", method="text")).strip()
            if sec_text:
                sections.append({"title": sec_title, "text": sec_text})

        if not title and not summary:
            return None

        return MedlineTopicRecord(
            topic_id=topic_id,
            title=title or "Medical Information",
            summary=summary or title,
            url=url,
            date_created=date_created,
            keywords=keywords,
            mesh_headings=mesh_headings,
            sections=sections
        )

    @staticmethod
    def _lenient_regex_parse(path: Path) -> List[MedlineTopicRecord]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

        topics = []
        # Find all <health-topic ...>...</health-topic> blocks
        blocks = re.findall(r'<health-topic\b([^>]*)>(.*?)</health-topic>', content, re.DOTALL | re.IGNORECASE)
        for idx, (attrs, body) in enumerate(blocks):
            title_match = re.search(r'title=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            title = title_match.group(1) if title_match else f"Topic {idx+1}"
            
            id_match = re.search(r'id=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            topic_id = id_match.group(1) if id_match else f"MP-{idx+1:04d}"
            
            summary_match = re.search(r'<full-summary[^>]*>(.*?)</full-summary>', body, re.DOTALL | re.IGNORECASE)
            if summary_match:
                clean_sum = re.sub(r'<[^>]+>', ' ', summary_match.group(1))
                clean_sum = re.sub(r'\s+', ' ', clean_sum).strip()
            else:
                clean_sum = title
                
            topics.append(MedlineTopicRecord(
                topic_id=topic_id,
                title=title,
                summary=clean_sum
            ))
        return topics
