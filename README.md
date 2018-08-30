# django-input-collection
[WARNING: PRE-ALPHA] Axis Checklists 3.0 and related user data collection

Below are the high-level dev promises for our use of this package in Axis and elsewhere.

* Replacement for checklists annotations
* Support for Django 1.11 and 2.0
* Build off of base questions concepts
* Supports parent / child questions (conditional)
* Understands single source of truth for a point in time.
  * Point in time is the active/latest program..
  * Still to decide are these bound to the home or program..
* Will utilize sections to help facilitate UI Groupings
* Will utilize django field rendering techniques
  * Initial support for Int, float, multiple choice, open
  * Initial support for choices via API (Users)
* May support scoping choices based on stimulus (simulation data)
* May support the notion of signal handling - 'program_recalculate'
