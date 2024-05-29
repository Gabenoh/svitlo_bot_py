import unittest
from unittest.mock import patch, MagicMock
import asyncio
from selenium.webdriver.common.by import By
from main import send_daily_message, get_all_user, bot


class TestSendDailyMessage(unittest.TestCase):

    @patch('main.get_all_user')
    @patch('main.bot.send_photo')
    @patch('main.driver')
    def test_send_daily_message(self, mock_driver, mock_send_photo, mock_get_all_user):
        # Mock user data
        mock_get_all_user.return_value = [{'id': '1', 'user': '123456', 'turn': 'A'}]

        # Mock WebDriver methods
        mock_driver.get.return_value = None
        mock_driver.find_element.return_value = MagicMock()
        mock_driver.find_element().get_attribute.return_value = '<svg>...</svg>'

        # Call the function
        asyncio.run(send_daily_message())

        # Assert that methods were called
        mock_driver.get.assert_called_with("https://svitlo.oe.if.ua")
        mock_driver.find_element.assert_called_with(By.ID, "todayGraphId")
        mock_send_photo.assert_called_once()


if __name__ == '__main__':
    unittest.main()
