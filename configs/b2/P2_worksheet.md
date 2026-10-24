# B2 worksheet - P2 Productivity assistant

You are configuring this pipeline **by hand**. This is the comparison against
the automated framework, so work as a developer would: read the project, decide
what suits it, write the descriptions, try things on development data.

Budget: **120 minutes of active work** for this project. Keep your own
count of time actually spent working, excluding breaks and excluding time spent
waiting for the model.

Do not open the test split. It is locked by the code anyway.

---

## 1. The project you are configuring

# P2 — Productivity assistant

Written 11 October 2026, before any development run. Frozen: any edit after
this commit is a protocol change and must be logged in `docs/decisions.md`.
Author-written, which is recorded as a limitation in the paper.

## Purpose

An assistant inside a work productivity suite. It takes a typed or spoken
instruction and turns it into an action in the user's calendar, mailbox or
lists, so the user does not have to open the app and click through it.

## Users

Working people at a desk or on a phone, usually mid-task and in a hurry. They
dictate naturally and often pack several details into one sentence: who, what,
when and where all at once.

## Supported requests

Calendar: create an event, cancel or delete an event, and ask what is on the
calendar.

Email: send an email, search or ask about mail, add a contact, and look up a
contact's details.

Lists: create a list or add items to one, ask what is on a list, and remove
items from a list.

## What it must pull out of a request

Dates and times; the name of an event; the name of a list; a person, and a
person's relationship to the user ("my manager", "mum"); an email address; a
mail folder; a place or business; how often something recurs; and the kind of
personal detail being asked for when the user asks about a contact.

Many requests carry several of these at once, and a missed detail means the
wrong action is taken, so recall of these fields matters as much as getting
the action right.

## Out of scope

Anything that is not calendar, email or lists. Playing media, weather, news,
general knowledge questions, transport, food ordering and device control belong
to other parts of the suite, and should be refused rather than mapped onto the
nearest supported action.

## Constraints

Requests run against the user's real mailbox and calendar, so a wrong action is
expensive to undo and a confidently wrong answer is worse than a refusal. Every
reply must be machine-readable by the suite's backend. It uses one small local
language model, for privacy reasons: the user's mail and calendar content must
not leave the machine. The user is waiting for the result, so it must feel
responsive, though a short pause is acceptable for a long instruction.

## What success looks like

The right one of the three areas and the right action within it; every detail
the user gave is carried through rather than dropped; and requests belonging to
other parts of the suite are refused clearly.

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
calendar_query: 
calendar_remove: 
calendar_set: 
email_addcontact: 
email_query: 
email_querycontact: 
email_sendemail: 
lists_createoradd: 
lists_query: 
lists_remove: 
```

---

## 4. Write a description for each kind of information

Say what the field holds, in the project's own terms.

```
app_name: 
artist_name: 
business_name: 
business_type: 
date: 
device_type: 
drink_type: 
email_address: 
email_folder: 
event_name: 
general_frequency: 
house_place: 
list_name: 
meal_type: 
media_type: 
music_descriptor: 
music_genre: 
person: 
personal_info: 
place_name: 
relation: 
song_name: 
sport_type: 
time: 
timeofday: 
transport_type: 
```

---

## 5. Your effort, in your own words

Fill these in before running `finish`. Be accurate rather than flattering;
an honest number is the whole point of this baseline.
Write each answer on its own line inside the box below, after the colon;
the notes under the box only explain the fields.

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

Each time you run `python scripts/run_b2.py check --project P2`, the
result is appended below. Every check counts toward your effort and toward
B2's design cost.

<!-- checks appended below this line -->
