"""Fake Anthropic client/messages for offline tests (tests/script, tests/review)."""

from types import SimpleNamespace


class FakeMessage:
    def __init__(self, content, stop_reason="end_turn", parsed=None, usage=None):
        self._content = content
        self.stop_reason = stop_reason
        self.parsed_output = parsed
        self._request_id = "req_test"
        self.usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            output_tokens_details=SimpleNamespace(thinking_tokens=100),
            **(usage or {}),
        )

    def model_dump(self, mode="json"):
        d = {"content": self._content, "stop_reason": self.stop_reason}
        if self.parsed_output is not None:
            d["parsed_output"] = self.parsed_output.model_dump(mode="json")
        return d


class FakeClient:
    def __init__(self, messages):
        self._queue = list(messages)
        self.requests = []
        self.messages = self

    def create(self, **request):
        self.requests.append(request)
        return self._queue.pop(0)

    def parse(self, **request):
        self.requests.append(request)
        return self._queue.pop(0)


def text_block(text, citations=None):
    return {"type": "text", "text": text, "citations": citations}


def cite(doc, start, end, cited_text):
    return {
        "type": "content_block_location",
        "document_index": doc,
        "start_block_index": start,
        "end_block_index": end,
        "cited_text": cited_text,
        "document_title": "x",
    }


EN_A = [
    "Adults with ADHD show a more frequent use of non-adaptive emotion regulation strategies.",
    "Emotion dysregulation was associated with symptom severity.",
    "The studies found were scarce and heterogeneous.",
]
EN_B = [
    "Children with ADHD show greater emotion dysregulation than peers.",
    "Effects were moderate in size across samples.",
]
