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
  twostage       one call for the intent, then one for that intent's fields  ……..
  schema         one call, with your written descriptions included in the prompt

Example selection
  fixed          the same one example per intent every time
  sim            the examples most similar to each request...……..

Out-of-scope policy
  llm            the model may answer none_of_the_above
  tfidf          a similarity threshold rejects a request before any model call......

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

**twostage-sim-tfidf** (replace the placeholder with one id):

```
CONFIG: twostage-sim-tfidf
```

---

## 3. Write a description for each request type

These go into the prompt for schema-guided configurations, and the framework's
Analyzer writes its own version of exactly this. One short line each. Leave a
line blank if you want no description for it.

```
alarm_query: Requests to check or list existing alarms.
alarm_remove: Requests to cancel or delete an alarm.
alarm_set: Requests to create or schedule a new alarm.
iot_cleaning: Requests to start or stop the cleaning robot.
iot_coffee: Requests to start the coffee machine.
iot_hue_lightchange: Requests to change the colour of a light.
iot_hue_lightdim: Requests to reduce the brightness of a light.
iot_hue_lightoff: Requests to switch a light off.
iot_hue_lighton: Requests to switch a light on.
iot_hue_lightup: Requests to increase the brightness of a light.
iot_wemo_off: Requests to switch a smart plug or socket off.
iot_wemo_on: Requests to switch a smart plug or socket on.
```

---

## 4. Write a description for each kind of information

Say what the field holds, in the project's own terms.

```
alarm_type: Type or label of an alarm mentioned by the user.
business_name:
business_type:
change_amount: Amount or percentage by which a device setting should change.
coffee_type:
color_type: Colour requested for a connected light, such as red, blue, or green.
date: Date or day mentioned for an alarm, such as tomorrow or Monday.
device_type: Household device mentioned, such as a light, cleaning robot, coffee machine, or smart plug.
event_name:
general_frequency: Repetition frequency explicitly mentioned for an alarm, such as daily or every weekday.
house_place: Room or location inside the home, such as bedroom, kitchen, or living room.
order_type:
place_name:
player_setting:
relation:
time: Specific clock time mentioned for an alarm, such as 6 AM or 8:30 PM.
time_zone:
timeofday: Part of the day mentioned for an alarm, such as morning or evening.```

---

## 5. Your effort, in your own words

Fill these in before running `finish`. Be accurate rather than flattering;
an honest number is the whole point of this baseline.

```
ACTIVE_MINUTES: 38
AI_ASSISTANCE: used the internet and Claude's explanation of the configuration options and terms (plus the scripts/b2_examples.py example viewer) to understand them; chose the configuration and wrote all descriptions myself
NOTES: I selected twostage-sim-tfidf because the two-stage approach first identifies the user's intent and then extracts the required information. Similarity-based examples help the model understand different ways of expressing commands. TF-IDF helps reject requests outside the supported tasks. A possible disadvantage is that the two-stage approach requires two model calls, which may increase response time. TF-IDF may also reject some valid requests with unusual wording.
```

- `38`: minutes you actually spent working on this, excluding
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

### Check 1 - 2026-10-24 16:20

- configuration: `twostage-sim-tfidf`
- descriptions written: 12 intents, 9 fields
- intent macro-F1 **0.858**, entity F1 0.586, out-of-scope F1 0.588, schema validity 1.000
- logical calls 139, physical 0
