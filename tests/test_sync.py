import unittest
from unittest.mock import Mock
from sync import SourceError, fetch_snapshot, tracker_data


def response(body, status=200):
    result = Mock(status_code=status, content=b"{}")
    result.json.return_value = body
    return result


class TrackerSourceTests(unittest.TestCase):
    def test_blocked_request_does_not_become_a_missing_profile(self):
        session = Mock()
        session.get.return_value = response({}, 403)
        with self.assertRaisesRegex(SourceError, "HTTP 403"):
            tracker_data(session, "profile/riot/test")

    def test_explicit_private_response_does_not_request_history(self):
        session = Mock()
        session.get.return_value = response({"errors": [{"code": "CollectorResultStatus::Private"}]})
        snapshot = fetch_snapshot(session, {"region": "eu", "gameName": "Player", "tagLine": "TR1"})
        self.assertEqual(snapshot["reason"], "private")
        self.assertIsNone(snapshot["profile"])
        self.assertEqual(session.get.call_count, 1)

    def test_partial_history_failure_keeps_profile_and_encoded_riot_id(self):
        session = Mock()
        profile = {"platformInfo": {"platformUserHandle": "Çelik Pilot#아이스"}}
        session.get.side_effect = [response({"data": profile}), response({}, 503)]
        snapshot = fetch_snapshot(session, {"region": "eu", "gameName": "Çelik Pilot", "tagLine": "아이스"})
        self.assertEqual(snapshot["profile"], profile)
        self.assertIsNone(snapshot["history"])
        self.assertIn("%C3%87elik%20Pilot%23%EC%95%84%EC%9D%B4%EC%8A%A4", session.get.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
