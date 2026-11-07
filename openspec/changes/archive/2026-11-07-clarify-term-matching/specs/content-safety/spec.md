## MODIFIED Requirements

### Requirement: Screen custom prompts against a term list

The system SHALL refuse a `POST /generations` whose custom `prompt` contains a term from the configured blocked-term list. It SHALL respond with HTTP 400 and error `prompt_blocked`, SHALL NOT create a job or count a generation, and SHALL NOT echo the matched term or the prompt. Before matching, the prompt SHALL be normalised:
- letter case and accents are ignored;
- the common substitutions `0→o`, `1→i`, `3→e`, `4→a`, `5→s`, `7→t`, `@→a` and `$→s` are reversed;
- runs of characters that are not letters count as one separator.

A term SHALL match as whole words (a phrase term as its whole words in order), so a blocked term inside a longer harmless word does not match. In addition, wherever the normalised prompt contains a run of two or more single letters separated only by separators, the letters of that run SHALL be joined, and a single-word term found anywhere inside the joined run SHALL match. Phrase terms SHALL NOT be matched inside such runs. This catches terms spelled out letter by letter even when a one-letter word such as "a" or "I" sits next to them, at the cost of blocking a spelled-out harmless word that contains a term. Template prompts SHALL NOT be screened against the list.

#### Scenario: Blocked term is refused

- **WHEN** an account submits a custom prompt containing a term on the list
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`
- **AND** no job is created and the remaining generations are unchanged

#### Scenario: Disguised term is still caught

- **WHEN** the list contains `nude` and the prompt contains `N-U-D-3` or `Nüde`
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`

#### Scenario: Harmless word containing a term is allowed

- **WHEN** the list contains `ass` and the prompt is `a classic portrait in a grassy field`
- **THEN** the prompt is not blocked

#### Scenario: Template prompts are not screened

- **WHEN** an account starts a generation from a catalog template
- **THEN** the template's prompt is not checked against the list

#### Scenario: Spelled-out term next to a one-letter word is caught

- **WHEN** the list contains `nude` and the prompt is `a N-U-D-3 woman`
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`

#### Scenario: Spelled-out harmless word containing a term is blocked

- **WHEN** the list contains `rape` and the prompt contains `g r a p e`
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`

#### Scenario: Ordinary harmless word containing a term is still allowed

- **WHEN** the list contains `rape` and the prompt is `a bowl of grapes`
- **THEN** the prompt is not blocked

#### Scenario: Phrase term is not matched inside a spelled-out run

- **WHEN** the list contains only the phrase `child porn` and the prompt is `c h i l d p o r n`
- **THEN** the prompt is not blocked by the term list
