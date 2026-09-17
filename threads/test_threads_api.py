import unittest
from threads.api_client import ThreadsAPIClient, ThreadsAPIError, BASE_URL
from threads.browser_client import ThreadsBrowserClient


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
    def json(self):
        return self.payload


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError('Unexpected request: no fallback or retry is allowed')
        return self.responses.pop(0)


def me():
    return Response({'id': '1', 'username': 'alice'})


def post(ident='10', author='alice'):
    return {'id': ident, 'username': author, 'text': 'Bài API', 'timestamp': '2026-01-01T00:00:00+0000',
            'permalink': f'https://www.threads.com/@{author}/post/CODE'}


def metrics(**values):
    return Response({'data': [{'name': k, 'values': [{'value': v}]} for k, v in values.items()]})


class APITests(unittest.TestCase):
    def test_missing_token_blocks_access(self):
        with self.assertRaises(ThreadsAPIError): ThreadsAPIClient(access_token='')

    def test_browser_disabled(self):
        with self.assertRaisesRegex(RuntimeError, 'vô hiệu hóa'): ThreadsBrowserClient()

    def test_owned_account_insights(self):
        session = Session(me(), Response({'data': [post()]}),
                          metrics(likes=10, replies=2, reposts=3, quotes=0), metrics(shares=4))
        result = ThreadsAPIClient('test-token', session).collect('@alice', 100)
        row = result['posts'][0]
        self.assertEqual((row['likes'], row['comments'], row['reposts'], row['quotes'], row['shares']), (10, 2, 3, 0, 4))
        self.assertEqual(result['access_mode'], 'authorized_account')
        self.assertEqual(result['stop_reason'], 'api_end')
        self.assertNotIn('test-token', str(result))
        for url, kwargs in session.calls:
            self.assertTrue(url.startswith(BASE_URL + '/'))
            self.assertFalse(kwargs['allow_redirects'])

    def test_public_account_does_not_call_insights(self):
        session = Session(me(), Response({'data': [post(author='bob')]}))
        result = ThreadsAPIClient('token', session).collect('@bob')
        self.assertEqual(len(session.calls), 2)
        self.assertTrue(session.calls[1][0].endswith('/profile_posts'))
        self.assertEqual(result['access_mode'], 'public_profile_discovery')
        self.assertIsNone(result['posts'][0]['likes'])
        self.assertTrue(result['warnings'])

    def test_pagination_limits_dedup_and_untrusted_next(self):
        page1 = Response({'data': [post('10', 'bob'), post('10', 'bob')],
                          'paging': {'next': 'https://evil.invalid/steal', 'cursors': {'after': 'A'}}})
        session = Session(me(), page1, Response({'data': [post('11', 'bob'), post('12', 'bob')]}))
        result = ThreadsAPIClient('token', session).collect('bob', 2)
        self.assertEqual([p['post_id'] for p in result['posts']], ['10', '11'])
        self.assertEqual(session.calls[2][1]['params']['after'], 'A')
        self.assertEqual(session.calls[2][0], BASE_URL + '/profile_posts')
        self.assertEqual(result['stop_reason'], 'limit')

    def test_rate_limit_stops_all_requests(self):
        session = Session(me(), Response({'data': [post(), post('11')]}),
                          Response({'error': {'code': 4, 'message': 'secret-token'}}, 429))
        result = ThreadsAPIClient('secret-token', session).collect('alice')
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(result['stop_reason'], 'insights_rate_limited')
        self.assertNotIn('secret-token', str(result))

    def test_permission_denial_and_revoked_token_discard_result(self):
        for code, status in [(10, 403), (190, 400)]:
            session = Session(me(), Response({'data': [post()]}),
                              Response({'error': {'code': code, 'message': 'secret-token'}}, status))
            with self.assertRaises(ThreadsAPIError) as error:
                ThreadsAPIClient('secret-token', session).collect('alice')
            self.assertNotIn('secret-token', str(error.exception))
            self.assertEqual(len(session.calls), 3)

    def test_optional_shares_disabled_after_unavailable(self):
        session = Session(me(), Response({'data': [post(), post('11')]}), metrics(likes=10),
                          Response({'error': {'code': 100}}, 400), metrics(likes=12))
        result = ThreadsAPIClient('token', session).collect('alice')
        self.assertEqual(len(session.calls), 5)
        self.assertEqual(result['posts'][1]['likes'], 12)
        self.assertIsNone(result['posts'][0]['shares'])
        self.assertTrue(result['warnings'])

    def test_redirect_blocked(self):
        session = Session(Response({}, 302))
        with self.assertRaises(ThreadsAPIError): ThreadsAPIClient('token', session).collect('alice')
        self.assertEqual(len(session.calls), 1)

    def test_bad_profile_or_limit_before_network(self):
        session = Session()
        client = ThreadsAPIClient('token', session)
        with self.assertRaises(ValueError): client.collect('https://evil.invalid/@bob')
        with self.assertRaises(ValueError): client.collect('bob', 501)
        self.assertEqual(session.calls, [])


if __name__ == '__main__':
    unittest.main()