# B2 worksheet - P1 Home assistant

You are configuring this pipeline **by hand**. This is the comparison against
the automated framework, so work as a developer would: read the project, decide
what suits it, write the descriptions, try things on development data.

Budget: **120 minutes of active work** for this project. Keep your own
count of time actually spent working, excluding breaks and excluding time spent
waiting for the model.

Do not open the test split. It is locked by the code anyway.

---

## 1. The project you are configuring

# P1 — Home assistant

Written 11 October 2026, before any development run. Frozen: any edit after
this commit is a protocol change and must be logged in `docs/decisions.md`.
Author-written, which is recorded as a limitation in the paper.

## Purpose

A voice and text assistant built into a home speaker. It handles two things
for the household: alarms, and control of the connected devices in the house.

## Users

People at home speaking or typing short, casual requests, often while doing
something else. They do not know the product's internal vocabulary and will
phrase the same thing many ways ("lights off", "kill the lights", "turn the
lamp off in here").

## Supported requests

Alarms: set an alarm, remove an alarm, and ask what alarms exist.

Devices: switch lights on and off, change a light's colour, dim or brighten a
light, start or stop the cleaning robot, start the coffee machine, and switch a
smart plug or socket on or off.

## What it must pull out of a request

The time or date an alarm refers to; which room or place in the house is meant;
which kind of device is meant; a colour; and how much to change something by.
Anything the user names that the assistant cannot act on should not be invented
into one of these fields.

## Out of scope

Anything that is not an alarm or a device in the house. Weather, news, music,
general questions, cooking, social posts and shopping are other products'
jobs. The assistant should say it cannot handle those rather than guess at the
closest supported action.

## Constraints

It replies while the user is still standing there, so responses must feel
immediate. It runs on modest hardware in the home and uses one small local
language model. Every reply must be machine-readable by the device firmware
that consumes it, because a malformed reply means the device does nothing.
Acting on the wrong device is worse than admitting the request was not
understood.

## What success looks like

Common requests are understood regardless of phrasing; the room or device
named by the user is the one acted on; and requests outside the two supported
areas are refused rather than forced into a supported action.

---

## 2. Pick a configuration

The twelve configurations combine three choices. Pick one id.

Extraction strategy
  joint          one call returns the intent and the information together
  twostage       one call for the intent, then one for that intent's fields
  schema         one call, with your written descriptions included in the prompt

Example selection
  fixed          the same one example per intent every time
  sim            the examples most similar to each request

Out-of-scope policy
  llm            the model may answer none_of_the_above
  tfidf          a similarity threshold rejects a request before any model call

Configuration ids are <extraction>-<examples>-<oos>, for example joint-sim-llm.

Available ids:
  joint-fixed-llm
  joint-fixed-tfidf
  joint-sim-llm
  joint-sim-tfidf
  twostage-fixed-llm
  twostage-fixed-tfidf
  twostage-sim-llm
  twostage-sim-tfidf
  schema-fixed-llm
  schema-fixed-tfidf
  schema-sim-llm
  schema-sim-tfidf

**Your choice** (replace the placeholder with one id):

```
CONFIG: <put one configuration id here>
```

---

## 3. Write a description for each request type

These go into the prompt for schema-guided configurations, and the framework's
Analyzer writes its own version of exactly this. One short line each. Leave a
line blank if you want no description for it.

```
alarm_query: 
alarm_remove: 
alarm_set: 
iot_cleaning: 
iot_coffee: 
iot_hue_lightchange: 
iot_hue_lightdim: 
iot_hue_lightoff: 
iot_hue_lighton: 
iot_hue_lightup: 
iot_wemo_off: 
iot_wemo_on: 
```

---

## 4. Write a description for each kind of information

Say what the field holds, in the project's own terms.

```
alarm_type: 
business_name: 
business_type: 
change_amount: 
coffee_type: 
color_type: 
date: 
device_type: 
event_name: 
general_frequency: 
house_place: 
order_type: 
place_name: 
player_setting: 
relation: 
time: 
time_zone: 
timeofday: 
```

---

## 5. Your effort, in your own words

Fill these in before running `finish`. Be accurate rather than flattering;
an honest number is the whole point of this baseline.

```
ACTIVE_MINUTES: 0
AI_ASSISTANCE: none
NOTES:
```

- `ACTIVE_MINUTES`: minutes you actually spent working on this, excluding
  breaks and excluding model waiting time.
- `AI_ASSISTANCE`: `none`, or describe exactly what help you used and for what.
  The plan requires this because the same person builds the automated system
  and this manual baseline, which biases the effort comparison.
- `NOTES`: anything about why you chose what you chose. This becomes part of
  the record for the paper.

---

## 6. Development checks

Each time you run `python scripts/run_b2.py check --project P1`, the
result is appended below. Every check counts toward your effort and toward
B2's design cost.

<!-- checks appended below this line -->
