---
title: Reasons to do an AI PhD in 2026
date: 2026/08/27
abstract: To discover insights about intelligence && To discover capabilities that don't lie on the scaling axis yet -- inherenent intelligence. 
draft: false
---

## AI research not for capabilities, but for insights about intelligence

By no means am I anti-LLM or anti-scaling-law. In fact, I am truly impressed by the progress we’ve had with this paradigm in the past 2 years[^1], and I believe any paradigm shifts we have in the future should only be valid if it could utilize the reasoning and agentic capabilities elicited by LLMs. Yet, when compared to reading classical ML literature, such as Graves’ Neural Turing Machine or Schmidhuber’s Fast Weight Programmers, I can’t help but to feel a sense of dissatisfaction with the work that is done by frontier AI recently. 

I’ve come to realize this is because:

> I don’t love AI research only for its capabilities, but more for the insights about intelligence that it reveals. 

Most announcements nowadays celebrate the former while reveal little of the latter. Frontier AI seems to love the narrative that new capabilities are entirely “emergent” so the public could be convinced of their AGI magic. In contrast, classical ideas from the earlier days were more like a rejection sampling process where the surviving techniques reveal some secrets about how our brains may work. In turn, we become better learners ourselves, adopting the formalisms derived from some of these winning solutions.

For instance, the effectiveness of Monte Carlo tree search in AlphaGo was one of the starting points for me. By no means is it the full story of reasoning, but it made me consider the importance of keeping sufficient breadth in our reasoning, exploring multiple options at the same level, while also going deep enough to get a good proxy for whether a given reasoning trace will succeed. At the same time, we shouldn't go too deep: in a deep rabbit hole, the information gain becomes noisy, and at that point it's better to invest more in breadth so we don't miss obvious solutions.

Or take continual learning as another example, a topic that I plan to study during my PhD. I found it to be such an incredible coincidence that one of the best solutions to catastrophic forgetting, in both humans and models, turns out to be revision with spaced repetition.[^2] When models and humans alike are placed under the constraint of online learning, we both forget, to a certain degree, the knowledge learnt in the past; the best solution seems to be keeping a replay buffer so we can revisit the concepts. Luckily, the revisits can get sparser and sparser.

How we train a modern LLM also has a couple of close resemblances with how the human brain learns:

<details markdown="block">
<summary>Click to expand the examples</summary>

* Pre-training resembles how humans first learn a new subject: a supervised process in which we absorb as much knowledge as possible from a static textbook, or imitate coaches and experts. This phase is sufficient to make us knowledgeable enough to hold a conversation on the topic, even to start teaching it, and it is also a necessary phase before we can begin exploring on our own, driven by curiosity. Models are the same: a sufficient warm start is almost necessary for a stable RL (post-training) phase. And even without post-training and alignment, a pre-trained model is already knowledgeable enough to do some pretty interesting things.
* The importance of RL in sharpening and refining a model's capabilities, whether in question answering or in specific knowledge domains, is also similar to humans in the sense that we have to practice. Practice is essential for a good grade in the final exam, or a good match if that's what you're chasing. We have to solve real problems. We can't just work in sim or in the textbook; we have to receive real human feedback in order to improve along the axes that real life measures. This mirrors RLHF and RLVR and their importance in post-training.
* More interestingly, we're starting to realize that RL is very sensitive to whether it is on-policy, and that on-policy RL may natively suffer less catastrophic forgetting than plain SFT. This too resembles how humans learn: it matters that we make mistakes ourselves rather than only learning from other people's, and that we understand topics in our own words. Both make things much easier to remember and to incorporate into our existing knowledge tree.
</details>

Obviously, these resemblances are nowhere near rigorous, but I still get extremely excited whenever I find them. It feels like I have learned something more about myself and grown the bubble of what we know about human intelligence. In a way, this matches the thesis I wrote on my homepage about a year ago: AI, to me, is both an end in itself (replicating these capabilities so it can do amazing things) and, more importantly, a means for us to understand human intelligence.

It is fair to say that the question of "who we are and what our minds are made of" has been one of the central mysteries of humanity. The importance of this question is why people are excited about developing AGI, but also nervous about the possibility of this problem being solved, as it seems to entail that perhaps nothing is left for us humans to do. Nevertheless, I think the outlook is still optimistic. I suggest we all treat capabilities research less as the end itself and more as a means. It is just an accelerated path towards better understanding ourselves and becoming better versions of ourselves.

## AI research without scaling (yet) — inherent intelligence

The idea in the previous section is in no way novel. In some sense, it is just a reminder of the different roles of research (understanding and science) and engineering (doing and products). Though for some reason, people seem to have forgotten the importance of both sides of the coin in recent times.

That said, I'd like to think that the role of academia is not reduced to merely understanding things. The tradition of academia being the source of new fundamental capabilities in AI is, I believe, here to stay. The only thing that has shifted is "what should be counted as new fundamental capabilities".

My current answer to this question is **"inherent intelligence"**: the types of intelligence that we have had since we were young, that are very hard to teach but still require taming over time, and that eventually become very important in defining who we are and the values we can create. To measure "inherentness", one can find a point on the spectrum of **teachability**. Common examples of "unsolved intelligences" that lie on the far end of this spectrum are, roughly in increasing order of inherentness: abstraction, creativity, efficient continual learning[^3], theory of mind, and emotion. It seems that the degree of inherentness is also proportional to how far we are from solving these parts of intelligence.[^4]

The idea of teachability is literal and simple: one just has to ask how hard it is to teach a certain capability to a pupil. Consider the classes we took as we grew up. There are classes like math and science, which I call knowledge classes: they have discrete concepts to be taught, and standard exams can evaluate a student's knowledge to a high degree. The variance of takeaways from these classes is generally lower, since the knowledge is mostly non-ambiguous.

In contrast, there are classes like problem solving, art, and design. Take CSC207, Software Design, offered at UofT, as an example. Ideas like clean code, code smells, and dependency injection are taught, and one could ace the exam by studying all these nice design principles. But the "art of programming" and the reasons behind these principles take a good programmer years to truly grasp. This is what I mean by a less teachable set of skills, and learning by doing becomes necessary.

Then there are things like theory of mind, emotional intelligence, creativity, and efficient continual learning. Rarely do we get taught these, though it is true that we get "inspired" by quotes and by people on how to improve ourselves along these axes. The closest education has come to training students in these areas is letting them "do their own thing" while providing mentorship and resources, which has been successful to some degree but is still largely unsolved. In fact, some of these, such as creativity, are so hard to even define clearly that a large part of a person's capability in them seems more inherent than taught.[^5]

Post-LLM AI started from the very "teachable" side of the spectrum, relying on pretraining and SFT, but has slowly progressed towards the other end with the adoption of large-scale RL, enabling interesting behaviors like reasoning and problem solving. The idea of the bitter lesson, or any scaling argument, seems to indicate that this trend of diffusing coverage across the spectrum of capabilities could continue simply by scaling up the data, model, and RL environments. I think we have to take a step back and define what it means for a scaling law to be valid. A scaling law only exists for a capability when that capability can be mapped onto the following equation:

$$\text{learning efficiency} \;\times\; \text{data availability} \;\propto\; \text{capability}$$

To be clear, for capabilities already mapped onto this equation, I expect scale to keep winning. I once underestimated this myself by fixating on the learning inefficiency term, while the data availability term kept growing. This is especially true considering how "chat" is such a universal interface for almost all use cases and how much human feedback is available from good product-data flywheels.

On the other end, people often abuse the bitter lesson nowadays to dismiss any attempt that does not utilize scale. What they don't realize is that many capabilities can't even be mapped onto this axis yet, and a lot of creative and down-to-earth efforts have to be tried before we even find the right mapping. How does one even define creativity or continual learning (mapping onto the RHS; some early examples for [creativity](https://arxiv.org/pdf/2605.16477) and [continual learning](https://philarchive.org/archive/RENTSR))? Even if we could define them one day, how are we supposed to have large enough training data or environments to elicit these behaviors? And for cases where data availability is inevitably scarce, one must rely on efficient continual learning, which we are nowhere near solving yet.

This kind of creative, ground-up work (defining these intelligences and finding their mappings onto the axis) is exactly the kind of fundamental capability research that academia has always been the source of.

If you are proud of who you are and how far you've come since you were young, you should be impressed and humbled by how brilliant a biological machine you have behind your eyes. This alone should be sufficient to convince you that there is so much work to be done to replicate the nuances of this machine. This is my belief and why I decided to do a PhD. I think there are still decades of interesting research ahead of us, and I hope you will think so too.

[^1]: E.g., closing the gap on the ARC-AGI series.

[^2]: With some extremely handwavy generalization that shouldn't affect the argument's validity.

[^3]: By continual learning, I don't merely mean that models can continually learn, or more autonomously iterate on whatever feedback or learning signal they have. There are some very important constraints that make it interesting. It is online: there is a single stream of incoming learning signal (or in-context signal) from which sufficient signal must be extracted. The rewards are extremely unverified, so we need some way of extracting signal from the stream of data. The models will forget, and it is impossible to keep the entire stream of context in a buffer, which means we need a very efficient learning algorithm, one that can learn virtually everything from its own stream of experience without the help of anyone else. To do this, the model probably has to actively change and interact with its environment so that it acquires the signals it needs from a really sparse set of rewards. More importantly, as my advisor argues, the self requires learning: if there is some sort of self in the model, it is because this entire stream of information is acquired by the model itself, and the ordering of this information is very important in constituting what counts as an experience for the model, and hence what constitutes its self. Framed this way, continual learning becomes a problem of reward modeling, of online gradient descent, of learning efficiency, and more, which is why I consider it quite the central problem of what you could call AGI.

[^4]: It is important to note that this spectrum only applies to those interested in human-inspired AI and the higher-order intelligences of humans. I am one of them. AI in the sense of learning statistical distributions, multimodal understanding, or robotics doesn't seem to map well onto this spectrum, but these problems are still very hard and interesting on their own.

[^5]: Perhaps RL is all you need to solve this. But "RL" is doing a lot of heavy lifting in such a statement: what is the reward along these axes? How can a model learn efficiently when the signals are so sparse? How do we even define creativity?
