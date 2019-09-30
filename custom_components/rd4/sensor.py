"""
Sensor component for rd4
Inspired by: Pippijn Stortelder
Current Version: 1.0.0 20190901 - John Peskens
20190901 - Initial

Description:
Save this file as [homeassistant]/config/custom_components/rd4/sensor.py

    Main resources options:
    restafval
    snoeiafval op afspraak
    kerstbomen
    best-tas
    gft
    oud papier
    pmd-afval

Example config:
Configuration.yaml:
  sensor:
    - platform: rd4
      wastecollector: rd4              (required)
      resources:                       (at least 1 required)
        - restafval
        - gft
        - oud papier
        - pmd-afval
      postcode: 1111AA                 (required)
      streetnumber: 1                  (required)
"""
import logging
from datetime import datetime
from datetime import timedelta
from datetime import date
from lxml.html import etree
from requests.exceptions import HTTPError
import dateparser
import requests
import urllib
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_RESOURCES)
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
CONF_WASTE_COLLECTOR = 'wastecollector'
CONF_POSTCODE = 'postcode'
CONF_STREET_NUMBER = 'streetnumber'

ATTR_FRIENDLY_NAME = 'friendly_name'
ATTR_WASTE_COLLECTOR = 'wastecollector'
ATTR_PICKUP_DATE = 'pickup_date'
ATTR_FRACTION_ID = 'ID'
ATTR_LAST_UPDATE = 'Last update'
ATTR_HIDDEN = 'Hidden'

COLLECTOR_URL = 'https://www.rd4info.nl/NSI/Burger/Aspx/afvalkalender_public_text.aspx'

RENAME_TITLES = {
    'restafval': 'Restafval',
    'snoeiafval op afspraak': 'Snoeiafval op afspraak',
    'kerstbomen': 'Kerstbomen',
    'best-tas': 'BEST-tas',
    'gft': 'GFT',
    'oud papier': 'Oud papier',
    'pmd-afval': 'PMD-afval',
}

FRACTION_ICONS = {
    'gft': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzEwOSAyMjQ4YzAsMCAtNTEzLDQzNyAtMTg2LDEwOTMgMTA3LDIxMyAxOTUsMzQ0IDI2NSw0MjQiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE5NzggMzY1MGM4NDMsLTcyOCAtNTksLTE2MzEgLTU5LC0xNjMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMzY3IDIxNjBjMCwwIDMyNyw4NjMgLTg3LDE1MTkiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTI5NTQgMzc1MWMtMTU5LC0xNzMgLTUzMiwtNjI5IC00MDEsLTk2OCA3NSwtMTk1IDI4NCwtNDM0IDQwMiwtNTY0Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yOTk1IDIxNzFjLTE1MCwtODIgLTQwNSwtMTYxIC03MDYsMzAgLTExLDAgLTY4OSwtMzcwIC05NDAsLTE5NiAtMjUxLDE3NCAxNzUsLTE5NiAxNzUsLTE5NiAwLDAgNjgxLC00NjYgMTIxNCwtMzkgNyw2IDE0LDEyIDIxLDE4IDExLDAgNjU2LC01MTIgMTE2OSwyMiAtMTEsMCAtNzMyLDY1IC03ODcsNDU3IC00LDQgLTU3LC00NiAtMTQ3LC05NnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE1NjkgMzgxMmMxMzEsMTIwIDQyNiw1NDQgMTAyNyw3NiAwLDAgNDkyLDQ0NiAxMDM4LDEzMCAtMTEsMCAyOTUsLTc2IDQwNCwtNDM1IC03NywzMyAtMjQwLDI1MCAtNjAxLDEyMCAwLDAgLTQwNCwyNjEgLTcyMSwtMTA5IDAsLTIyIC00OTIsMTc0IC02OTksMCAwLC0xMSAtMzE3LDIzOSAtNTc5LC00MyAwLDAgMCwxNDEgMTMxLDI2MXptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzQ3MCAxMDk4YzAsMCAtNzA5LDE0MiAtNjk4LDYzMyAtMTEsMCAtMjI5LC0yNzMgNjExLC04MjlsODcgMTk2em0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
    'gft': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzEwOSAyMjQ4YzAsMCAtNTEzLDQzNyAtMTg2LDEwOTMgMTA3LDIxMyAxOTUsMzQ0IDI2NSw0MjQiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE5NzggMzY1MGM4NDMsLTcyOCAtNTksLTE2MzEgLTU5LC0xNjMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMzY3IDIxNjBjMCwwIDMyNyw4NjMgLTg3LDE1MTkiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTI5NTQgMzc1MWMtMTU5LC0xNzMgLTUzMiwtNjI5IC00MDEsLTk2OCA3NSwtMTk1IDI4NCwtNDM0IDQwMiwtNTY0Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yOTk1IDIxNzFjLTE1MCwtODIgLTQwNSwtMTYxIC03MDYsMzAgLTExLDAgLTY4OSwtMzcwIC05NDAsLTE5NiAtMjUxLDE3NCAxNzUsLTE5NiAxNzUsLTE5NiAwLDAgNjgxLC00NjYgMTIxNCwtMzkgNyw2IDE0LDEyIDIxLDE4IDExLDAgNjU2LC01MTIgMTE2OSwyMiAtMTEsMCAtNzMyLDY1IC03ODcsNDU3IC00LDQgLTU3LC00NiAtMTQ3LC05NnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTE1NjkgMzgxMmMxMzEsMTIwIDQyNiw1NDQgMTAyNyw3NiAwLDAgNDkyLDQ0NiAxMDM4LDEzMCAtMTEsMCAyOTUsLTc2IDQwNCwtNDM1IC03NywzMyAtMjQwLDI1MCAtNjAxLDEyMCAwLDAgLTQwNCwyNjEgLTcyMSwtMTA5IDAsLTIyIC00OTIsMTc0IC02OTksMCAwLC0xMSAtMzE3LDIzOSAtNTc5LC00MyAwLDAgMCwxNDEgMTMxLDI2MXptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMzQ3MCAxMDk4YzAsMCAtNzA5LDE0MiAtNjk4LDYzMyAtMTEsMCAtMjI5LC0yNzMgNjExLC04MjlsODcgMTk2em0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
    'glas': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8bGluZSBjbGFzcz0iZmlsMCBzdHIwIiB4MT0iMjUxNiIgeTE9IjExNzIiIHgyPSIyNzE5IiB5Mj0gIjExNzIiIC8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0zMTUyIDE5OTZjLTcyLC04MCAtMTY1LC0xMDcgLTIyNCwtMTM1IC01OCwtMjcgLTY0LC0xMDAgLTY0LC0xMTcgMCwtMTcgMSwtNTAwIDEsLTUzMyAwLC0zMyAxOCwtNDggMTgsLTQ4IDU0LDAgNjksLTM4IDczLC02MCAyLC05IDIsLTUwIDIsLTUwIDAsLTQyIC0yNywtNzYgLTY5LC03NmwtNDIgLTYzIC00NTIgMCAtNDIgNjNjLTY1LDAgLTcxLDc2IC03MSw3NiAwLDUgMCw0MyAxLDQ3IDcsMzYgNDAsNjMgNzgsNjMgMCwwIDE2LDEyIDE2LDQ4IDAsMzYgMTEsNTE2IDExLDUzMyAwLDE4IC0xMyw4MCAtNzIsMTE5IC01NCwzNiAtMTQzLDYwIC0yMTYsMTMyIC0xNDAsMTM4IC0xMzcsMjk0IC0xMzcsNTAzbDAgMTU2NmMwLDE1MyAxNSwzMTcgMjcwLDMyNyAwLDEgNzY1LC0xIDc2NSwwIDI0MiwtMTUgMjg5LC0xNzYgMjg5LC0zMjdsMCAtMTU2NmMwLC0yMDggMTUsLTMzNSAtMTM3LC01MDN6bTAgMHoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAgc3RyMCIgZD0iTTIyNjcgNDM5M2M1MSwtODIgMjI1LC0xNzUgMzcxLC0xNzUgMTQ2LDAgMjU4LDYzIDM2NSwxNzVsLTczNSAwem0wIDB6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yMjY3IDQzOTNjNTEsLTgyIDIyNSwtMTc1IDM3MSwtMTc1IDE0NiwwIDI1OCw2MyAzNjUsMTc1bC03MzUgMHptMCAweiIvPg0KIDwvZz4NCjwvc3ZnPg0K',
    'oud papier': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNTI3NSAyNjY1YzAsMTQ0MSAtMTE2OCwyNjEwIC0yNjEwLDI2MTAgLTE0NDEsMCAtMjYxMCwtMTE2OCAtMjYxMCwtMjYxMCAwLC0xNDQxIDExNjgsLTI2MTAgMjYxMCwtMjYxMCAxNDQxLDAgMjYxMCwxMTY4IDI2MTAsMjYxMHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMTMzNiAzNjkwYy05MywyMyAtMTkwLDQ0IC0yOTQsNjJsMTM3OCA4NTBjMCwwIDEwMzgsLTIxIDE5NzMsLTEzNTVsLTIwNCAtMTMxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0xMzkxIDMzNzRjLTExMSwzMiAtMjMxLDYyIC0zNjMsODlsMTM5OCA4MTVjMCwwIDExMTUsLTE4NyAxOTM4LC0xNDA0bC0yMzYgLTEzOSIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMTQzMyAzMzQ5bDkzNyA1MzFjMCwwIDEwMzcsLTYwIDE5MjAsLTE0MjlsLTQ5NiAtMjkxIi8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0xNDk3IDI5MjRjLTE3MCw2NCAtMzI1LDExMiAtNTM1LDE1OGw0NzEgMjY3Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik0yNDA0IDc3NmMwLDAgMTMsNzA0IC0yNTMsMTExNiAwLDAgLTM5Miw4NjQgLTEyNTYsNjc4bDE0MjggODE0YzQxLDI0IDg2LDQyIDEzMiw1MyAxNTcsMzggNDkyLDY0IDgxMiwtMjc2IDAsMCA1NzEsLTQ1MiA1ODUsLTE1NDJsLTE0NDkgLTg0NHptMCAweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNMjQ1OCA0NjQzYy0zNyw4IDczMywyNCAxOTQ4LC03MTlsLTMzMyAtMjE5YzAsMCAtNTEwLDY4OCAtMTYxNSw5Mzh6bTAgMHoiLz4NCiA8L2c+DQo8L3N2Zz4NCg==',
    'pmd-afval': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zNjExMWluIiBoZWlnaHQ9IjUuMzYxMTFpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTM2MSA1MzYxIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5maWwwIHtmaWxsOiMyMzFGMjA7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI2NzkgMTM4Yy0xNDAxLDAgLTI1NDEsMTE0MCAtMjU0MSwyNTQxIDAsMTQwMSAxMTQwLDI1NDEgMjU0MSwyNTQxIDE0MDEsMCAyNTQxLC0xMTQwIDI1NDEsLTI1NDEgMCwtMTQwMSAtMTE0MCwtMjU0MSAtMjU0MSwtMjU0MXptMCA1MjIwYy0xNDc3LDAgLTI2NzksLTEyMDIgLTI2NzksLTI2NzkgMCwtMTQ3NyAxMjAyLC0yNjc5IDI2NzksLTI2NzkgMTQ3NywwIDI2NzksMTIwMiAyNjc5LDI2NzkgMCwxNDc3IC0xMjAyLDI2NzkgLTI2NzksMjY3OXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTM3NTcgMjc3N2MwLDAgLTI4MSwtNzUgLTU3NiwybDU3NiAtMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0xNzAyIDI0NTVsLTE4MCAtMjY2IDQzMyA4MSAtMjUzIDE4NHptMjk5IC0xNzZjLTUsLTIzIC0yMywtNDAgLTQ2LC00NGwtNDMzIC04MWMtMjMsLTQgLTQ3LDYgLTU5LDI1IC0xMywyMCAtMTMsNDUgMCw2NWwxODAgMjY2YzksMTMgMjMsMjIgMzgsMjUgMywxIDcsMSAxMCwxIDEyLDAgMjQsLTQgMzQsLTExbDI1MyAtMTg0YzE5LC0xNCAyOCwtMzcgMjMsLTYweiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI3MzUgMzk0MmM0OSwwIDkzLC04IDkzLC04IDI2LC01IDUyLDkgNjMsMzIgMiwyIDksNSAyMiw1bDggMGM5LDAgMjAsMSAzMiwxIDY1LDAgODYsLTEwIDkwLC0xMyAxMCwtMjEgMzIsLTMzIDU1LC0zMiAxLDAgMjAsMSA0NSwxbC0yMSAxMTZjLTQyLDM5IC0xMTUsNDQgLTE3MCw0NCAtMTMsMCAtMjYsMCAtMzYsLTFsLTggMGMtNDYsLTEgLTc3LC0xNyAtOTYsLTM0IC0yMSwyIC00OSw1IC03OSw1bTU5NyAtMTMxOWM1LC04MiA5LC0xNTcgMTQsLTIxOSA1LC03NiA5LC0xMzcgOSwtMTYyIDAsLTEyIDAsLTI4IDEsLTQ3IDQsLTE1NyAxNCwtNTczIC0xNzMsLTgxNiAtMTUwLC0xOTUgLTE5MiwtMzMzIC0yMDIsLTQxMCAtMTAsMCAtMjEsMCAtMzIsMCAtNDAsMCAtNzYsLTEgLTEwOCwtMyAtMTIsMTAwIC01NSwzMDAgLTIwOCw0ODEgLTY1LDc3IC0xMzcsMjIxIC0xMzQsNDc3bC0xMTYgLTRjLTIsLTI4OSA4NCwtNDU2IDE2MSwtNTQ4IDE4MywtMjE3IDE4NSwtNDY4IDE4NSwtNDcxIDAsLTE3IDcsLTMzIDIwLC00NCAxMywtMTEgMzAsLTE2IDQ3LC0xMyAzNiw2IDg5LDkgMTUyLDkgNDksMCA4NiwtMiA4NiwtMiAxOCwtMSAzNSw3IDQ3LDIwIDEyLDE0IDE3LDMyIDEzLDQ5IDAsMCAtMTYsMTMyIDE4MCwzODggMjExLDI3NSAyMDEsNzIxIDE5Nyw4ODkgMCwxOCAtMSwzMyAtMSw0NCAwLDI5IC00LDg4IC05LDE3MCAtNCw2MiAtOSwxMzYgLTEzLDIxN2wtMTE2IC01eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTI4MjIgOTY2YzI5LDcgNjEsMTAgOTMsMTAgMzEsMCA1OCwtMyA3OSwtN2wwIC0xMTljLTU4LDUgLTEyNSwyIC0xNzEsLTNsLTEgMTE5em05MyAxMjZjLTYwLDAgLTExOCwtOSAtMTcxLC0yOCAtMjQsLTggLTM5LC0zMCAtMzksLTU1bDEgLTIzMGMwLC0xOCA4LC0zNCAyMiwtNDUgMTQsLTExIDMyLC0xNSA0OSwtMTEgMSwwIDY2LDE1IDE0OCwxNSA0MiwwIDgwLC00IDExNSwtMTEgMTcsLTQgMzUsMSA0OSwxMiAxNCwxMSAyMiwyOCAyMiw0NWwxIDIzM2MwLDI1IC0xNiw0OCAtNDEsNTYgLTMsMSAtNjcsMjEgLTE1NSwyMXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0yNzY0IDc3NmMwLDAgMTU4LC0zNCAyODQsNGwtMjg0IC00eiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMwNDggODM5Yy02LDAgLTExLC0xIC0xNywtMyAtMTA5LC0zMyAtMjUzLC0zIC0yNTQsLTMgLTMxLDcgLTYyLC0xMyAtNjksLTQ1IC03LC0zMSAxMywtNjIgNDUsLTY5IDcsLTIgMTc1LC0zNyAzMTMsNSAzMSw5IDQ4LDQyIDM4LDczIC04LDI1IC0zMSw0MSAtNTYsNDF6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzE0OSA0MDAxYzQ4LDIzIDE1OCw2NSAzMTMsNjUgMTA1LDAgMjE0LC0xOSAzMjMsLTU3bDAgLTEwNTUgLTUyIC0xMDNjLTU2LDEwIC0xNTcsMjQgLTI4MywyNCAtOTAsMCAtMTc3LC04IC0yNTksLTIybC02MCA5OSAxNyAxMDUwem0zMTMgMTgxYy0yNDcsMCAtMzk2LC05MyAtNDAyLC05NyAtMTcsLTEwIC0yNywtMjkgLTI3LC00OGwtMTggLTExMDFjMCwtMTEgMywtMjIgOCwtMzFsOTAgLTE0OGMxMywtMjEgMzgsLTMyIDYyLC0yNyA4NiwxOCAxNzksMjggMjc2LDI4IDE3MywwIDMwMCwtMzAgMzAxLC0zMCAyNiwtNiA1NCw2IDY2LDMwbDc4IDE1NWM0LDggNiwxNyA2LDI2bDAgMTExMGMwLDI0IC0xNSw0NiAtMzcsNTQgLTEzNiw1MiAtMjcxLDc4IC00MDIsNzh6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzc1NyAyNzc3YzAsMCAtMjgxLC03NSAtNTc2LDJsNTc2IC0yeiIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCIgZD0iTTMxODAgMjgzN2MtMjYsMCAtNDksLTE3IC01NiwtNDMgLTgsLTMxIDEwLC02MyA0MiwtNzEgMzA3LC04MCA1OTQsLTYgNjA2LC0yIDMxLDggNDksNDAgNDEsNzEgLTgsMzEgLTQwLDQ5IC03MSw0MSAtMywtMSAtMjcwLC03MCAtNTQ2LDIgLTUsMSAtMTAsMiAtMTUsMnoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNzQ4IDQwODZsLTQyIDkyYzAsMCAtMTk2LDYwIC00ODcsLTExbC00MCAtODVjMCwwIDMwNCw5NCA1NjgsNXoiLz4NCiAgPHBhdGggY2xhc3M9ImZpbDAiIGQ9Ik0zNTAwIDQyNjBjLTk2LDAgLTE5NSwtMTIgLTI5NCwtMzcgLTE3LC00IC0zMSwtMTYgLTM5LC0zMmwtNDAgLTg1Yy0xMCwtMjEgLTYsLTQ1IDksLTYzIDE1LC0xNyAzOSwtMjQgNjEsLTE3IDEsMCAxMzQsNDEgMjk0LDQxIDg4LDAgMTY4LC0xMiAyMzcsLTM2IDIyLC03IDQ2LC0xIDYyLDE2IDE2LDE3IDE5LDQyIDEwLDYzbC00MiA5MmMtNywxNSAtMjAsMjcgLTM2LDMyIC0zLDEgLTg3LDI2IC0yMjQsMjZ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMzQ2MSAzMTAxYy0xMTksMCAtMjYxLC0xNSAtNDE5LC02MCAtMzEsLTkgLTQ5LC00MSAtNDAsLTcyIDksLTMxIDQxLC00OSA3MiwtNDAgNDMyLDEyMyA3MjksMyA3MzIsMiAzMCwtMTIgNjQsMiA3NiwzMSAxMiwzMCAtMiw2NCAtMzEsNzYgLTksNCAtMTU1LDYzIC0zODksNjN6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTU3NCA0MTQ4bDQyOCA5MiA2MzcgLTE0OSAwIC0xODg3IC02MzggMTE1Yy03LDEgLTEzLDEgLTIwLDBsLTQwNyAtNjkgMCAxODk5em00MjggMjA5Yy00LDAgLTgsMCAtMTIsLTFsLTQ4NiAtMTA0Yy0yNywtNiAtNDYsLTI5IC00NiwtNTdsMCAtMjAxNWMwLC0xNyA4LC0zMyAyMSwtNDQgMTMsLTExIDMwLC0xNiA0NywtMTNsNDY1IDc5IDY5NiAtMTI2YzE3LC0zIDM0LDIgNDgsMTMgMTMsMTEgMjEsMjcgMjEsNDVsMCAyMDAzYzAsMjcgLTE5LDUxIC00NSw1N2wtNjk1IDE2MmMtNCwxIC05LDIgLTEzLDJ6Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIiBkPSJNMTUxNSAyMjM4Yy0yOCwwIC01MiwtMjAgLTU3LC00OCAtNiwtMzIgMTUsLTYyIDQ3LC02OGw2ODggLTEyM2M2LC0xIDEyLC0xIDE4LDBsNDgwIDY5YzMyLDUgNTQsMzQgNDksNjYgLTUsMzIgLTM0LDU0IC02Niw0OWwtNDcxIC02NyAtNjc5IDEyMWMtMywxIC03LDEgLTEwLDF6Ii8+DQogIDxwb2x5Z29uIGNsYXNzPSJmaWwwIiBwb2ludHM9IjE5MzIsNDI5OSAyMDQ4LDQyOTkgMjA0OCwyMjYxIDE5MzIsMjI2MSAiLz4NCiA8L2c+DQo8L3N2Zz4NCg==',
    'restafval': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+DQo8IS0tIENyZWF0b3I6IENvcmVsRFJBVyBYNiAtLT4NCjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWw6c3BhY2U9InByZXNlcnZlIiB3aWR0aD0iNS4zMzMzM2luIiBoZWlnaHQ9IjUuMzMzMzNpbiIgdmVyc2lvbj0iMS4xIiBzdHlsZT0ic2hhcGUtcmVuZGVyaW5nOmdlb21ldHJpY1ByZWNpc2lvbjsgdGV4dC1yZW5kZXJpbmc6Z2VvbWV0cmljUHJlY2lzaW9uOyBpbWFnZS1yZW5kZXJpbmc6b3B0aW1pemVRdWFsaXR5OyBmaWxsLXJ1bGU6ZXZlbm9kZDsgY2xpcC1ydWxlOmV2ZW5vZGQiDQp2aWV3Qm94PSIwIDAgNTMzMyA1MzMzIg0KIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4NCiA8ZGVmcz4NCiAgPHN0eWxlIHR5cGU9InRleHQvY3NzIj4NCiAgIDwhW0NEQVRBWw0KICAgIC5zdHIwIHtzdHJva2U6IzIzMUYyMDtzdHJva2Utd2lkdGg6MTExLjExfQ0KICAgIC5maWwwIHtmaWxsOm5vbmU7ZmlsbC1ydWxlOm5vbnplcm99DQogICBdXT4NCiAgPC9zdHlsZT4NCiA8L2RlZnM+DQogPGcgaWQ9IkxheWVyX3gwMDIwXzEiPg0KICA8bWV0YWRhdGEgaWQ9IkNvcmVsQ29ycElEXzBDb3JlbC1MYXllciIvPg0KICA8cGF0aCBjbGFzcz0iZmlsMCBzdHIwIiBkPSJNNDUyNCA0MjQxYzQ4LC0zOTggMTksLTU1OCAtMTM4LC04MDMgLTE1NiwtMjQ1IC0xMDczLC0xMzEyIC0xMDczLC0xMzEybDM5MSAxMDA5IC01MjYgLTg0NiAtMjAzIDExMzUgLTExIC0xMTU0IC05MDEgNDMyIDk1MSAtNjQxIDMzOSA3NCAxMDEzIC01NDIgLTY5NSAtMTU2IC0yNzcgNDc3IDg3IC0xMDMzIC02ODkgNjAxIDEzNyAtMjM3IC01OTYgLTMwOSA0NTEgOTQzIC0xOTc0IDkyMyAtMjE3IDUyMyAyMTYgNTIwIC0xNjEgLTY3IC0xNTEgMzQwbTM5ODMgNDIxYzIwLC0xMjcgMzUsLTIzMSA0MywtMjk5Ii8+DQogIDxwYXRoIGNsYXNzPSJmaWwwIHN0cjAiIGQ9Ik01Mjc1IDI2NjVjMCwxNDQxIC0xMTY4LDI2MTAgLTI2MTAsMjYxMCAtMTQ0MSwwIC0yNjEwLC0xMTY4IC0yNjEwLC0yNjEwIDAsLTE0NDEgMTE2OCwtMjYxMCAyNjEwLC0yNjEwIDE0NDEsMCAyNjEwLDExNjggMjYxMCwyNjEwem0wIDB6Ii8+DQogPC9nPg0KPC9zdmc+DQo=',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCES, default=[]): cv.ensure_list,
    vol.Required(CONF_POSTCODE, default='1111AA'): cv.string,
    vol.Required(CONF_STREET_NUMBER, default='1'): cv.string,
    vol.Optional(CONF_WASTE_COLLECTOR, default='rd4'): cv.string,
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug('Setup Rest API retriever')

    postcode = config.get(CONF_POSTCODE)
    street_number = config.get(CONF_STREET_NUMBER)
    waste_collector = config.get(CONF_WASTE_COLLECTOR).lower()
    resources = config.get(CONF_RESOURCES)

    try:
        data = WasteData(postcode, street_number, waste_collector, resources, hass)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    entities = []
    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()
        entities.append(WasteSensor(data, sensor_type, waste_collector))

    add_entities(entities)

class WasteData(object):

    def __init__(self, postcode, street_number, waste_collector, resources, hass):
        self.data = None
        self.postcode = postcode
        self.street_number = street_number
        self.waste_collector = waste_collector
        self.main_url = COLLECTOR_URL
        self.resources = resources
        self.hass = hass

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        _LOGGER.debug('Updating Waste collection dates using Rest API')

        try:
            url = self.main_url + '?pc=' + self.postcode + '&nr=' + self.street_number + '&t='
            req = urllib.request.Request(url=url)
            f = urllib.request.urlopen(req)
            response = f.read()
            if response:
                dom = etree.HTML(response)
                tables = dom.xpath(".//table[@class='plaintextMonth']")
                today = datetime.combine(date.today(), datetime.min.time())
                data1 = []
                idx = 1
                for table in tables:
                    rows = iter(table)
                    for row in rows:
                        values = [col.text for col in row]
                        if values:
                            pickupdate = dateparser.parse(values[0])
                            title = values[1].lower()
                            if pickupdate >= today and title in self.resources:
                                if not any(title in sublist['sensor'] for sublist in data1):
                                     data1.append({'id': idx, 'pickupdate': pickupdate.strftime('%d-%m-%Y'), 'title': RENAME_TITLES[title], 'icon_data': title, 'timestamp': pickupdate.timestamp(), 'sensor': 'sensor.' + self.waste_collector + '_' + title})
                                     idx = idx + 1

                response = data1
                def sort_On_Date(elem):
                    return elem['timestamp']
                response.sort(key=sort_On_Date)
                data1 = []

                for key in response:
                    data1.append(key['sensor'].replace('-', '_').replace(' ', '_'))
                self.hass.states.set('group.rd4', 'on', {'entity_id': data1, 'friendly_name': 'RD4 pickup date'})
            if not response:
                _LOGGER.error('Address not found!')
            else:
                self.data = response

        except HTTPError as exc:
            _LOGGER.error('Error occurred while fetching data: %r', exc)
            self.data = None
            return False

class WasteSensor(Entity):

    def __init__(self, data, sensor_type, waste_collector):
        self.data = data
        self.sensor_type = sensor_type
        self.waste_collector = waste_collector
        self._name = waste_collector + ' ' + self.sensor_type
        self._unit = ''
        self._hidden = False
        self._entity_picture = None
        self._state = None
        self._friendly_name = None
        self._pickup_date = None
        self._fraction_id = None
        self._last_update = None

    @property
    def name(self):
        return self._name

    @property
    def entity_picture(self):
        return self._entity_picture

    @property
    def state(self):
        return self._state

    @property
    def friendly_name(self):
        return self._friendly_name

    @property
    def device_state_attributes(self):
        return {
            ATTR_FRIENDLY_NAME: self._friendly_name,
            ATTR_WASTE_COLLECTOR: self.waste_collector,
            ATTR_PICKUP_DATE: self._pickup_date,
            ATTR_FRACTION_ID: self._fraction_id,
            ATTR_LAST_UPDATE: self._last_update,
            ATTR_HIDDEN: self._hidden
        }

    @property
    def unit_of_measurement(self):
        return self._unit

    def update(self):
        self.data.update()
        waste_data = self.data.data
        today = datetime.today()
        retrieved_data = 0
        try:
            for key in waste_data:
                if key['icon_data'] == self.sensor_type:
                    self._friendly_name = key['title']
                    self._fraction_id = key['id']
                    self._state = key['pickupdate']
                    if self.sensor_type in FRACTION_ICONS:
                        self._entity_picture = FRACTION_ICONS[self.sensor_type]
                    self._last_update = today.strftime('%d-%m-%Y %H:%M')
                    self._hidden = False

                    if key['pickupdate'] == today.strftime('%d-%m-%Y'):
                        self._pickup_date = 'on'
                    else:
                        self._pickup_date = 'off'
                    retrieved_data = 1

            if retrieved_data == 0:
                self.set_state_none()

        except ValueError:
            self.set_state_none()

    def set_state_none(self):
        self._state = None
        self._friendly_name = None
        self._pickup_date = None
        self._fraction_id = None
        self._hidden = True
