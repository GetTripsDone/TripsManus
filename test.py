import asyncio

from app.agent.search_poi_navi import SearchPOINavi
from app.logger import logger
import json


async def main():
    agent = SearchPOINavi()
    try:
        # prompt = input("Enter your prompt: ")
        # pois = [['天安门', '1', ''], ['雍和宫', '2', ''], ['天坛公园', '2', '']]
        # prompt = json.dumps(pois, ensure_ascii=False)

        routes = {'day1': {'r1': [["天安门", "116.397455,39.909187", "1", "B000A60DA1", "010"], ["雍和宫", "116.417296,39.947239", "2", "B000A7BGMG", "010"]], 'r2': [["天坛公园", "116.410829,39.881913", "2", "B000A81CB2", "010"], ["雍和宫", "116.417296,39.947239", "2", "B000A7BGMG", "010"]]}}
        prompt = json.dumps(routes, ensure_ascii=False)
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")


if __name__ == "__main__":
    asyncio.run(main())
