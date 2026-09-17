import pytest

from seatdata._batch import normalize_batch_response, prepare_batch_payload


class TestPrepareBatchPayload:
    def test_int_ids_pass_through(self):
        assert prepare_batch_payload([105294241, 105288127], None) == {
            "event_ids_sh": [105294241, 105288127]
        }

    def test_str_ids_coerced_to_int(self):
        assert prepare_batch_payload(None, ["225220", "225221"]) == {"event_ids": [225220, 225221]}

    def test_mixed_int_and_str_duplicate_collapses_to_one(self):
        assert prepare_batch_payload([225220, "225220"], None) == {"event_ids_sh": [225220]}

    def test_whitespace_and_leading_zero_strings_coerce_to_same_id(self):
        assert prepare_batch_payload([" 225220", "0225220"], None) == {"event_ids_sh": [225220]}

    def test_dedup_preserves_first_seen_order(self):
        assert prepare_batch_payload([3, 1, 3, 2, 1], None) == {"event_ids_sh": [3, 1, 2]}

    def test_dedup_is_per_list_not_cross_list(self):
        assert prepare_batch_payload([225220], [225220]) == {
            "event_ids_sh": [225220],
            "event_ids": [225220],
        }

    def test_sh_only_call_omits_event_ids_key(self):
        assert "event_ids" not in prepare_batch_payload([1], None)

    def test_event_ids_only_call_omits_sh_key(self):
        assert "event_ids_sh" not in prepare_batch_payload(None, [1])

    def test_both_none_raises(self):
        with pytest.raises(ValueError, match="Either event_ids_sh or event_ids must be provided"):
            prepare_batch_payload(None, None)

    def test_both_empty_raises(self):
        with pytest.raises(ValueError, match="Either event_ids_sh or event_ids must be provided"):
            prepare_batch_payload([], [])

    def test_bare_string_argument_raises(self):
        with pytest.raises(ValueError, match="event_ids_sh"):
            prepare_batch_payload("225220", None)

    def test_bare_bytes_argument_raises(self):
        with pytest.raises(ValueError, match="event_ids"):
            prepare_batch_payload(None, b"225220")

    def test_non_iterable_argument_raises(self):
        with pytest.raises(ValueError, match="event_ids_sh"):
            prepare_batch_payload(225220, None)

    def test_none_element_raises(self):
        with pytest.raises(ValueError, match="None"):
            prepare_batch_payload([225220, None], None)

    def test_bool_element_raises(self):
        with pytest.raises(ValueError, match="True"):
            prepare_batch_payload([True], None)

    def test_float_element_raises(self):
        with pytest.raises(ValueError, match="105294241.9"):
            prepare_batch_payload([105294241.9], None)

    def test_non_numeric_string_element_raises(self):
        with pytest.raises(ValueError, match="abc"):
            prepare_batch_payload(["abc"], None)

    def test_nested_container_element_raises(self):
        with pytest.raises(ValueError):
            prepare_batch_payload([[225220]], None)

    def test_100_unique_ids_allowed(self):
        payload = prepare_batch_payload(list(range(1, 51)), list(range(51, 101)))
        assert len(payload["event_ids_sh"]) + len(payload["event_ids"]) == 100

    def test_101_unique_ids_raises(self):
        with pytest.raises(ValueError, match="at most 100 unique event ids"):
            prepare_batch_payload(list(range(1, 52)), list(range(52, 102)))

    def test_dedup_happens_before_count_check(self):
        ids = list(range(1, 101)) + [1, 2, 3]
        assert prepare_batch_payload(ids, None) == {"event_ids_sh": list(range(1, 101))}


class TestNormalizeBatchResponse:
    def test_full_body_passes_through(self):
        body = {
            "results": {"1": [{"price": 10}]},
            "errors": {"2": "not_found"},
            "sources": {
                "1": [
                    {
                        "source": "sh",
                        "collecting_since": "2024-03-01",
                        "tracked_for_event": True,
                        "status": "ok",
                    }
                ]
            },
        }
        assert normalize_batch_response(body) == body

    def test_missing_errors_filled_with_empty_dict(self):
        assert normalize_batch_response({"results": {}}) == {
            "results": {},
            "errors": {},
            "sources": {},
        }

    def test_missing_results_filled_with_empty_dict(self):
        assert normalize_batch_response({"errors": {}}) == {
            "results": {},
            "errors": {},
            "sources": {},
        }

    def test_none_body_normalized(self):
        assert normalize_batch_response(None) == {"results": {}, "errors": {}, "sources": {}}

    def test_none_values_normalized(self):
        assert normalize_batch_response({"results": None, "errors": None, "sources": None}) == {
            "results": {},
            "errors": {},
            "sources": {},
        }
