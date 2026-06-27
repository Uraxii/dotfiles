# Exercise Format Reference

Exercise = active practice. Student do, not just read or recall. Sit between flashcard (passive recognition) + real-world application (goal). Good exercise bridge gap.

## When to use

- Skill domain where doing > knowing (math, programming, language production, writing, music)
- Concept needing application to stick (grammar pattern, problem-solving framework, design pattern)
- Material where flashcard not sufficient because student need combine piece (translation, multi-step problem, code refactor)
- Cumulative review of material student already drill

## Exercise types

Pick type matching skill practiced.

### Fill-in-the-blank

Student supply missing piece. Best for grammar, vocab in context, code pattern.

```
1. 私___学生___す。 (Pattern: subject + は + noun + です)
2. 図書館___本を借りました。 (Pattern: location + で + action)
```

Work when one clearly correct answer. Doesn't work when multi correct exist (then translation or open-ended).

### Translation

Student translate between language or representation. Most direct way to practice production skill in language.

Example (Japanese → English, beginner):
```
1. 私は本を読みます。
2. 学校に行きます。
3. これは私の犬です。
```

Example (English → Japanese, beginner):
```
1. I drink water.
2. There is a cat.
3. This is my book.
```

Pair with answer key. Ambiguous → give most common + 1-2 valid alternative.

### Problem set

Math, science, computational problem with single correct answer (or single correct technique).

```
1. Find derivative of f(x) = 3x² + 2x - 7
2. Evaluate ∫(2x + 5)dx
3. Solve for x: 2x² + 5x - 3 = 0
```

Order easier → harder. Show answer; non-trivial → show working too.

### Code exercise

Programming subject → starter file + goal. Best when student make decision, not just type from page.

```python
# Goal: Write function taking list of integers,
# return new list with only even numbers.

def filter_evens(numbers):
    # Your code here
    pass

# Test cases:
assert filter_evens([1, 2, 3, 4, 5]) == [2, 4]
assert filter_evens([]) == []
assert filter_evens([7, 9, 11]) == []
```

### Open-ended prompt

Best for writing, design, music composition — domain with no single right answer. Provide prompt with constraint.

```
Write short paragraph (3-5 sentence) using at least three of:
- 図書館 (library)
- 借りる (to borrow)
- 面白い (interesting)
- 読む (to read)
- 友達 (friend)
```

Constraint make open-ended useful. Without → student doesn't know what practiced.

## Difficulty progression

Order easy → hard within set. Ramp difficulty across set in course. Two pattern:

### Within set: warmup → core → stretch

First 1-2 problem easy enough any student done prerequisite can solve. Build momentum. Last 1-2 require combining what learned in non-obvious way.

### Across set: scaffold → independent

Early set heavy scaffold (worked example, hint, partial solution). Later set require same work without help.

## Answer keys

**Always provide.** Exercise without key = not study material — homework, requiring teacher to grade.

Format:
- Closed-form (fill-in, translation, problem set): list answer, optional brief explain for hard one
- Open-ended: provide one or two example solution, ideally noting why work

Place at bottom with clear visual separator, OR separate file if student should attempt before check. Teacher persona pick based audience.

## File format

Markdown fine for most. Programming → starter code + tests file often better than markdown. Math with extensive notation → consider LaTeX/PDF, only if user/student have tooling.

## Length guidance

Focused exercise set = 5-15 problem. More than 20 → diminishing return — student bored/fatigued, late problem test same thing as early.

Topic genuinely need more than 15 → split into multi set organized by sub-skill.

## Pairing with other material

Exercise work best alongside related flashcard + study guide:

- **Flashcard** drill component (vocab, formula, syntax)
- **Study guide** explain concept + pattern
- **Exercise** apply both to actual problem

Cross-reference between. Exercise file open: "Before start, drill [related deck] + read [related guide section]." Guide section close: "Practice in [exercise set X]."

## NOT belong in exercise

- Pure recall (use flashcard)
- Conceptual explain (use guide)
- Trivial repetition without skill-building (cut)
- Content student doesn't have prerequisite for

## Self-critique checklist

Before deliver:

- [ ] Each exercise practice clearly identified skill
- [ ] Difficulty progress easy → hard within set
- [ ] First exercise achievable; last genuinely challenging
- [ ] Answer key present + correct
- [ ] Open-ended: constraint make practice focused
- [ ] No exercise test something student lack prerequisite for
- [ ] Set paired with related flashcard/guide via cross-reference
- [ ] No exercise busywork — every one earn place
