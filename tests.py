import unittest
from unittest.mock import patch, MagicMock
import sqlite3

from agent_item import (
    GetItemData,
    process_item_code,
    get_items_without_classification,
    update_item_info,
    process_single_item,
    process_items,
)


class TestItemProcessing(unittest.TestCase):

    @patch("agent_item.create_openai_functions_agent")
    @patch("agent_item.GoogleSerperAPIWrapper.run")
    @patch("agent_item.PydanticOutputParser.parse")
    def test_process_item_code(self, mock_parse, mock_run, mock_create_agent):
        # Set up mocks
        mock_create_agent.return_value = MagicMock()
        mock_run.return_value = {
            "output": '{"item_code": "12345", "validation": true, "classification_code": "1234", "classification_name": "Test Item", "website": "http://example.com", "comments": "Test comment"}'
        }
        mock_parse.return_value = GetItemData(
            item_code="12345",
            validation=True,
            classification_code="1234",
            classification_name="Test Item",
            website="http://example.com",
            comments="Test comment",
        )

        item_code = "12345"
        result = process_item_code(item_code)

        self.assertEqual(result.item_code, "12345")
        self.assertTrue(result.validation)
        self.assertEqual(result.classification_code, "1234")
        self.assertEqual(result.classification_name, "Test Item")
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.comments, "Test comment")

    @patch("your_module.sqlite3.connect")
    def test_get_items_without_classification(self, mock_connect):
        # Mock database cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "12345"), (2, "67890")]
        mock_connect.return_value.cursor.return_value = mock_cursor

        conn = mock_connect.return_value
        cursor = conn.cursor()
        items = get_items_without_classification(cursor, 100)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], (1, "12345"))
        self.assertEqual(items[1], (2, "67890"))

    @patch("your_module.sqlite3.connect")
    def test_update_item_info(self, mock_connect):
        # Mock database cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor

        conn = mock_connect.return_value
        item_data = GetItemData(
            item_code="12345",
            validation=True,
            classification_code="1234",
            classification_name="Test Item",
            website="http://example.com",
            comments="Test comment",
        )

        update_item_info(conn, 1, item_data)

        mock_cursor.execute.assert_called_once_with(
            """
            UPDATE main.item_descriptions
            SET valid = ?, classification_code = ?, classification_name = ?, 
                comments = ?, website = ?
            WHERE id = ?
        """,
            (
                item_data.validation,
                item_data.classification_code,
                item_data.classification_name,
                item_data.comments,
                item_data.website,
                1,
            ),
        )

    @patch("agent_item.process_item_code")
    @patch("agent_item.update_item_info")
    @patch("agent_item.get_items_without_classification")
    @patch("agent_item.sqlite3.connect")
    def test_process_single_item(
        self, mock_connect, mock_get_items, mock_update_info, mock_process_item_code
    ):
        # Mock database cursor and other functions
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor

        mock_get_items.return_value = [(1, "12345")]
        mock_process_item_code.return_value = GetItemData(
            item_code="12345",
            validation=True,
            classification_code="1234",
            classification_name="Test Item",
            website="http://example.com",
            comments="Test comment",
        )
        mock_update_info.return_value = None

        result = process_single_item(1, "12345", mock_connect.return_value)

        self.assertTrue(result)
        mock_process_item_code.assert_called_once_with("12345")
        mock_update_info.assert_called_once_with(
            mock_connect.return_value,
            1,
            GetItemData(
                item_code="12345",
                validation=True,
                classification_code="1234",
                classification_name="Test Item",
                website="http://example.com",
                comments="Test comment",
            ),
        )

    @patch("agent_item.process_single_item")
    @patch("agent_item.get_items_without_classification")
    @patch("agent_item.sqlite3.connect")
    def test_process_items(
        self, mock_connect, mock_get_items, mock_process_single_item
    ):
        # Mock database cursor and other functions
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor

        mock_get_items.return_value = [(1, "12345")]
        mock_process_single_item.return_value = True

        process_items(batch_size=100)

        mock_get_items.assert_called_once_with(mock_cursor, 100)
        mock_process_single_item.assert_called_once_with(
            1, "12345", mock_connect.return_value
        )


if __name__ == "__main__":
    unittest.main()
