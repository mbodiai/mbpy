import logging
import os

from dotenv import load_dotenv
from notion_client import Client

# Load environment variables from .env file
load_dotenv()

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def append_notion_table_row(new_data: dict, page_content: list = None, debug: bool = False):
    """Appends a new row to a Notion table using the Notion SDK. Supports fields like `title`, `select`, `multi_select`, `checkbox`, and `rich_text`. Optionally adds page content if provided.

    Args:
        new_data (dict): Row data where keys are column names and values are content. Supported types:
            - `title` (str): Primary title field.
            - `select` (str): Single option from a predefined list.
            - `multi_select` (list of str): Multiple options from a predefined list.
            - `checkbox` (bool): True/False field.
            - `rich_text` (str): Text with formatting support.
        page_content (list, optional): A list of blocks (e.g., paragraphs, bullet points) to append to the page linked to the first column (`Instruction`).
        debug (bool, optional): If True, logs debug information about the created row and response.
    
    Example:
        new_data = {
            "Instruction": "New Task",  # Title
            "Status": "In Progress",  # Select
            "Tags": ["Priority", "Development"],  # MultiSelect
            "Complete": False,  # Checkbox
            "Comments": "Sample comment"  # Rich Text
        }

    Example:
        page_content = [
            {"type": "paragraph", "content": "Task description"},
            {"type": "bulleted_list_item", "content": "First action point"}
        ]

    Returns:
        None
    """  # noqa: E501
    # Load API key and database ID from environment variables
    api_key = os.getenv("NOTION_API_KEY")
    database_id = os.getenv("NOTION_DATABASE_ID")

    notion = Client(auth=api_key)

    # Get the database schema (properties)
    database_info = notion.databases.retrieve(database_id=database_id)
    database_properties = database_info["properties"]

    # Create a new row in the database
    new_row = {
        "parent": {"database_id": database_id},
        "properties": {},
    }

    # Populate the properties for the new row based on the provided data
    for key, value in new_data.items():
        if key not in database_properties:
            logger.error(f"KeyError: '{key}' does not exist in the database schema.")
            continue  # Skip this key and move on to the next one

        property_type = database_properties[key]["type"]

        if property_type == "title":  # Title field
            new_row["properties"][key] = {
                "title": [{"text": {"content": value}}],
            }
        elif property_type == "select":  # Select field
            new_row["properties"][key] = {
                "select": {"name": value},
            }
        elif property_type == "multi_select":  # MultiSelect field
            new_row["properties"][key] = {
                "multi_select": [{"name": tag} for tag in value],
            }
        elif property_type == "checkbox":  # Checkbox field
            new_row["properties"][key] = {
                "checkbox": value,
            }
        elif property_type == "rich_text":  # Rich text field
            new_row["properties"][key] = {
                "rich_text": [{"text": {"content": value}}],
            }

    # Add the new row to the database
    page_response = notion.pages.create(**new_row)

    # If the user wants to add content to the first column's page, handle it here
    if page_content and "Instruction" in new_data:
        page_id = page_response["id"]
        
        # Convert the content into Notion block format
        blocks = []
        for item in page_content:
            if item["type"] == "paragraph":
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": item["content"]}}]},
                })
            elif item["type"] == "bulleted_list_item":
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": item["content"]}}]},
                })
        
        # Append the blocks to the page inside the 'Instruction' column
        notion.blocks.children.append(block_id=page_id, children=blocks)
    
    # Log the result
    if debug:
        logger.debug(f"Added new row with data: {new_data}")
        logger.debug(f"Response: {page_response}")
    else:
        logger.info("Row added to the database")


# Example usage
if __name__ == "__main__":

    # Example data for the new row
    new_data = {
        "Instruction": "New Task",  # This will be the first column (Title field)
        "Schema Used": ["None", "No Examples"],  # Example Select field
        "Example Schema": "Test",  # Example MultiSelect field
        "Agent": ["None", "No Examples"],  # Example Checkbox field
        "Response": "Test",  # Example Text field
        "Hardware": "Locobot", 
        "Comments": "Test",
        "Success": "True",
    }

    # Example page content to be added to the 'Instruction' page
    page_content = [
        {"type": "paragraph", "content": "This is a task description."},
        {"type": "bulleted_list_item", "content": "First action point"},
        {"type": "bulleted_list_item", "content": "Second action point"},
    ]

    # Call the function to append a new row with additional page content
    append_notion_table_row(new_data, page_content=page_content, debug=True)
