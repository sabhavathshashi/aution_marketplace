import unittest
from unittest.mock import patch

from app import app


class AuctionPermissionTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.secret_key = 'test-secret'

    def test_seller_sees_seller_controls_and_no_bid_form_on_own_auction(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 7
            session['role'] = 'Seller'

        class FakeCursor:
            def close(self):
                pass

        class FakeDB:
            def cursor(self, dictionary=False):
                return FakeCursor()

            def close(self):
                pass

        with patch('app.get_db_connection', return_value=FakeDB()), patch('app.get_auction_state', return_value=(
            {
                'auction_id': 1,
                'seller_id': 7,
                'title': 'Vintage Lamp',
                'description': 'A classic lamp',
                'current_price': 100.0,
                'status': 'ACTIVE',
                'end_time': '2026-07-04 10:00:00',
                'seller_name': 'Shashi'
            },
            []
        )):
            response = self.client.get('/auction/1')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('You are the seller of this auction.', html)
        self.assertNotIn('Place a Bid', html)

    def test_seller_cannot_place_bid_on_own_auction(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 7
            session['role'] = 'Seller'

        class FakeCursor:
            def close(self):
                pass

        class FakeDB:
            def cursor(self, dictionary=False):
                return FakeCursor()

            def close(self):
                pass

            def rollback(self):
                pass

        with patch('app.get_db_connection', return_value=FakeDB()), patch('app.get_auction_state', return_value=(
            {
                'auction_id': 1,
                'seller_id': 7,
                'title': 'Vintage Lamp',
                'description': 'A classic lamp',
                'current_price': 100.0,
                'status': 'ACTIVE',
                'end_time': '2026-07-04 10:00:00',
                'seller_name': 'Shashi'
            },
            []
        )):
            response = self.client.post('/auction/1', data={'bid_amount': '120'}, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(response.status_code, 403)
        self.assertIn('You cannot bid on your own auction.', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
