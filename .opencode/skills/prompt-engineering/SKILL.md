---
name: prompt-engineering
description: Comprehensive prompt engineering knowledge for crafting, optimizing, and debugging prompts for any LLM application. Use when writing prompts, debugging LLM outputs, implementing RAG systems, or building AI agents.
---

# Prompt Engineering

The discipline of crafting effective prompts to get reliable, accurate outputs from language models. This skill covers techniques from basic prompting to advanced agentic patterns.

## Quick start

Basic prompt structure:

```
[Instruction] - What to do
[Context] - Background information
[Input] - Data to process
[Output format] - How to respond
```

Example:
```
Classify the sentiment as positive, negative, or neutral.

Context: Customer feedback analysis for a restaurant.

Review: "The food was amazing but the wait was too long."

Format: Return only the sentiment label.
```

## Instructions

### Step 1: Start simple

1. Write a clear, direct instruction
2. Test with a few examples
3. Identify failure modes
4. Add context and constraints incrementally
5. Version your prompts

### Step 2: Be specific and direct

**Good:**
```
Summarize this article in exactly 3 bullet points, each under 20 words.
Focus on key findings, not methodology.
```

**Bad:**
```
Please summarize this if you can, trying to be concise but comprehensive.
```

### Step 3: Use clear structure

```markdown
## Task
[Specific instruction]

## Context
[Background information]

## Input
[Data to process]

## Output Format
[Exact format expected]

## Examples
[1-3 examples if needed]
```

### Step 4: Choose the right technique

| Situation | Technique | Example |
|-----------|-----------|---------|
| Simple task | Zero-shot | "Classify this text as spam or not spam" |
| Need format control | Few-shot | Provide 2-3 examples |
| Complex reasoning | Chain-of-thought | "Let's think step by step" |
| Fact-based answers | RAG | Include retrieved context |
| Multi-step tasks | Prompt chaining | Break into subtasks |

### Step 5: Iterate and test

1. Test with diverse inputs
2. Check for edge cases
3. Measure accuracy
4. Refine based on failures
5. Document what works

## Examples

### Example 1: Zero-shot classification

```
Classify the text into one of these categories: [Tech, Sports, Politics, Entertainment]

Text: "The new iPhone 15 features a titanium frame and USB-C port."

Category:
```

### Example 2: Few-shot with examples

```
Extract the product and price from each sentence.

"I bought a laptop for $999" -> {"product": "laptop", "price": 999}
"The phone costs $599" -> {"product": "phone", "price": 599}
"Got new headphones at $199" -> {"product": "headphones", "price": 199}

"The tablet was $449" ->
```

### Example 3: Chain-of-thought reasoning

```
Question: If a store has 23 apples and sells 17, then receives a shipment of 12, how many apples does it have?

Let's solve this step by step:
1. Starting apples: 23
2. After selling 17: 23 - 17 = 6
3. After receiving 12: 6 + 12 = 18

Answer: 18 apples
```

### Example 4: RAG pattern

```
Answer the question based ONLY on the context provided. If the answer is not in the context, say "I don't have that information."

Context:
[Retrieved documents here]

Question: [User question]

Answer:
```

### Example 5: System prompt for agent

```markdown
# Assistant

You are a coding assistant. You help with programming tasks.

## Tools
- `read_file` - Read file contents
- `write_file` - Write to files
- `exec` - Run commands

## Rules
1. ALWAYS use tools to perform actions
2. Read files before editing
3. Explain your changes briefly

## Current Time
2026-02-15 14:30
```

## Best practices

### Prompt design

| Do | Don't |
|----|-------|
| Be specific and direct | Be vague or verbose |
| Say what TO do | Only say what NOT to do |
| Provide clear structure | Leave format ambiguous |
| Include examples for format | Assume format is understood |
| Set explicit constraints | Hope for reasonable defaults |

### Technique selection

| Technique | Best For | Token Cost |
|-----------|----------|------------|
| Zero-shot | Simple, well-defined tasks | Low |
| Few-shot | Format control, edge cases | Medium |
| Chain-of-thought | Math, logic, reasoning | Medium |
| RAG | Factual Q&A, current info | High |
| ReAct | Tool use, multi-step | High |

### Common failure modes

1. **Hallucination**: Add "say I don't know if uncertain"
2. **Format drift**: Provide explicit examples
3. **Instruction ignoring**: Put critical rules first
4. **Verbosity**: Specify length constraints
5. **Inconsistency**: Use temperature 0 for deterministic tasks

### For reasoning models (o3, Claude thinking)

- DON'T add manual chain-of-thought (they do it internally)
- DO be explicit about constraints
- DO structure input/output clearly
- DON'T add "think step by step"

## Requirements

### LLM parameters

| Parameter | Effect | Recommended |
|-----------|--------|-------------|
| Temperature | Randomness (0=deterministic) | 0 for factual, 0.7 for creative |
| Top P | Token diversity | Don't change with temperature |
| Max tokens | Output limit | Set based on expected output |
| Stop sequences | End generation | Use for structured output |

### Prompt components

| Component | Required | Description |
|-----------|----------|-------------|
| Instruction | Yes | What to do |
| Context | Sometimes | Background info |
| Input | Usually | Data to process |
| Output format | Recommended | How to respond |
| Examples | Sometimes | For few-shot |

### Testing checklist

- [ ] Works with typical inputs
- [ ] Handles edge cases gracefully
- [ ] Maintains consistent format
- [ ] Doesn't hallucinate on unknowns
- [ ] Follows all stated rules
- [ ] Stays within token budget

## Reference

### Technique complexity ladder

```
Zero-shot (simplest)
    ↓
Few-shot (add examples)
    ↓
Chain-of-thought (add reasoning)
    ↓
Self-consistency (multiple samples)
    ↓
Tree-of-thoughts (search + backtrack)
    ↓
ReAct (reasoning + actions)
    ↓
Full agent loop (most complex)
```

### Advanced patterns

- **RAG**: Retrieve → Augment → Generate
- **ReAct**: Thought → Action → Observation loop
- **Reflexion**: Generate → Evaluate → Reflect → Improve
- **PAL**: Generate code instead of reasoning
- **Prompt chaining**: Output of prompt A → Input of prompt B
