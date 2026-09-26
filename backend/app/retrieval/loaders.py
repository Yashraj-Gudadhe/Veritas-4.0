"""
Streaming XML Loader — memory-efficient parser for large medical XML datasets.
Ported from Veritas-2.0 app/rag/loaders.py.

Used ONLY for the FAISS ingestion pipeline (replaces bulk XML loading).
xml_parser.py is NOT replaced — it stays for the /api/index/medlineplus endpoint.

All v2-specific imports removed. EvidenceCategory string values are inlined.
"""
import os
import uuid
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Generator, Optional, Dict, Any

from langchain_core.documents import Document

# Inline the one EvidenceCategory value needed — avoids any v2 import dependency
_MEDICAL_CONVERSATION = "medical_conversation"


def inspect_xml_schema(xml_path: "str | Path", max_depth: int = 4) -> Dict[str, Any]:
    """
    Inspects an XML file structure dynamically without hardcoding assumptions.
    Returns detected root tag, child tag candidates for conversations/turns, and attribute keys.
    Useful for adapting to unknown XML schemas before streaming.
    """
    schema_info: Dict[str, Any] = {
        "root_tag": None,
        "element_tags": set(),
        "attribute_keys": set(),
        "likely_conversation_tags": set(),
        "likely_turn_tags": set(),
        "sample_item_count": 0,
    }

    try:
        context = ET.iterparse(str(xml_path), events=("start",))
        for event, elem in context:
            tag_name = elem.tag.split("}")[-1]  # strip namespace prefix if present
            if schema_info["root_tag"] is None:
                schema_info["root_tag"] = tag_name
            else:
                schema_info["element_tags"].add(tag_name)
                for k in elem.attrib.keys():
                    schema_info["attribute_keys"].add(k)

                lower_tag = tag_name.lower()
                if any(
                    kw in lower_tag
                    for kw in ["conversation", "dialog", "qa", "record", "case", "consultation", "interaction"]
                ):
                    schema_info["likely_conversation_tags"].add(tag_name)
                if any(
                    kw in lower_tag
                    for kw in ["turn", "utterance", "message", "question", "answer", "doctor", "patient"]
                ):
                    schema_info["likely_turn_tags"].add(tag_name)

                schema_info["sample_item_count"] += 1
                if schema_info["sample_item_count"] >= 500:
                    break
    except Exception as e:
        print(f"[XML Schema Inspection Warning]: {e}")

    return schema_info


def stream_xml_conversations(
    xml_path: "str | Path",
    batch_size: int = 100,
) -> Generator[List[Document], None, None]:
    """
    Memory-efficient streaming parser for large medical XML conversation datasets.
    Yields batches of LangChain Document objects with rich conversation metadata.

    Designed for datasets with up to tens of thousands of conversations.
    Uses iterparse so only one element is held in memory at a time.

    Args:
        xml_path:   Path to the XML file.
        batch_size: Number of Documents per yielded batch.

    Yields:
        Batches of LangChain Document objects.
    """
    path_obj = Path(xml_path)
    if not path_obj.exists():
        return

    schema = inspect_xml_schema(path_obj)
    filename = path_obj.name

    # Determine conversation node tag from schema inspection
    conversation_tags = schema["likely_conversation_tags"]
    if not conversation_tags:
        # Fallback to common XML conversation tag names
        conversation_tags = {
            "conversation", "dialogue", "dialog", "record",
            "doc", "item", "case", "qa",
        }

    current_batch: List[Document] = []
    conv_counter = 0

    try:
        context = ET.iterparse(str(path_obj), events=("end",))
        for event, elem in context:
            tag_name = elem.tag.split("}")[-1]
            lower_tag = tag_name.lower()

            is_conv = lower_tag in {t.lower() for t in conversation_tags} or any(
                kw in lower_tag
                for kw in ["conversation", "dialog", "record", "qa"]
            )

            if is_conv:
                conv_counter += 1

                # Extract conversation ID from attributes or synthesise one
                conv_id = (
                    elem.attrib.get("id")
                    or elem.attrib.get("conversation_id")
                    or elem.attrib.get("convo_id")
                    or elem.attrib.get("qid")
                    or f"conv_{conv_counter}"
                )

                # Extract turn text and speaker labels
                turns: List[str] = []
                speaker_info: List[str] = []

                children = list(elem)
                if children:
                    for child in children:
                        c_tag = child.tag.split("}")[-1]
                        c_text = "".join(child.itertext()).strip()
                        c_speaker = (
                            child.attrib.get("speaker")
                            or child.attrib.get("role")
                            or c_tag
                        )
                        if c_text:
                            turns.append(f"{c_speaker}: {c_text}")
                            speaker_info.append(c_speaker)
                else:
                    # Flat text element (no child turns)
                    full_text = "".join(elem.itertext()).strip()
                    if full_text:
                        turns.append(full_text)

                if turns:
                    content_str = "\n".join(turns)
                    speakers_str = (
                        ", ".join(set(speaker_info)) if speaker_info else "Doctor, Patient"
                    )

                    doc = Document(
                        page_content=content_str,
                        metadata={
                            "conversation_id": str(conv_id),
                            "source_type": _MEDICAL_CONVERSATION,
                            "source_file": filename,
                            "source_name": f"Medical Conversation #{conv_id}",
                            "chunk_id": f"xml_{conv_id}_{uuid.uuid4().hex[:6]}",
                            "speaker": speakers_str,
                            "title": f"Medical Dialogue #{conv_id}",
                            "evidence_category": _MEDICAL_CONVERSATION,
                            "retrieval_timestamp": datetime.datetime.now(
                                datetime.timezone.utc
                            ).isoformat(),
                        },
                    )
                    current_batch.append(doc)

                # Free parsed element from memory immediately
                elem.clear()

                if len(current_batch) >= batch_size:
                    yield current_batch
                    current_batch = []

        # Yield any remaining items
        if current_batch:
            yield current_batch

    except Exception as e:
        print(f"[XML Streaming Parse Error in {filename}]: {e}")
        if current_batch:
            yield current_batch
