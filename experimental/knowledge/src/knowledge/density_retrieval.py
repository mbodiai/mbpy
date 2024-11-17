# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
# %% [markdown]
# # Density based retrieval relevance
#
# An important aspect of using embeddings-based retreival systems like Chroma is knowing whether there are relevant results to a given query in the existing dataset. As application developers, we would like to know when the system doesn't have enough information to complete a given query or task - we want to know what we don't know.
#
# This is particularly important in the case of retrieval-augmented generation, since it's [often been observed](https://arxiv.org/abs/2302.00093) that supplying irrelevant context serves to confuse the generative model, leading to the degredation of application performance in ways that are difficult to detect.
#
# Unlike a relational database which will not return results if none match the query, a vector search based retrieval system will return the $k$ nearest neighbors to any given query, whether they are relevant or not.
#
# One possible approach one might take is to tune a distance threshold, and reject any results which fall further away from the query. This might be suitable for certain kind of fixed datasets, but in practice such thresholds tend to be very brittle, and often serve to exclude many relevant results while not always excluding irrelevant ones. Additionally, the threshold will need to be continously adapted as the data changes. Additionally, such distance thresholds are not comparable across embedding models for a given dataset, nor across datasets for a given embedding model.
#
# We would prefer to find a data driven approach which can:
# - produce a uniform and comparable measure of relevance for any dataset
# - automatically adapt as the underlying data changes
# - is relatively inexpensive to compute
#
# This notebook demonstrates one possible such approach, which relies on the distribution of distances (pseudo 'density') between points in a given dataset. For a given result, we use compute the percentile the result's distance to the query falls into with respect to the overall distribution of distances in the dataset. This approach produces a uniform measure of relevance for any dataset, and is relatively cheap to compute, and can be computed online as data mutates.
#
# This approach is still very preliminary, and we welcome contributions and alternative approaches - some ideas are listed at the end of this notebook.
# %% [markdown]
# ## Preliminaries
# %%
# Install required packages

def main():
    import sys

    from IPython import get_ipython

    from mbpy.commands import run

    run("{sys.executable} -m pip install chromadb numpy umap-learn[plot] matplotlib tqdm datasets")

    # %% [markdown]
    # ### Dataset
    #
    # As a demonstration we use the [SciQ dataset](https://arxiv.org/abs/1707.06209), available from [HuggingFace](https://huggingface.co/datasets/sciq).
    #
    # Dataset description, from HuggingFace:
    #
    # > The SciQ dataset contains 13,679 crowdsourced science exam questions about Physics, Chemistry and Biology, among others. The questions are in multiple-choice format with 4 answer options each. For the majority of the questions, an additional paragraph with supporting evidence for the correct answer is provided.

    # %%
    # Get the SciQ dataset from HuggingFace
    from datasets import load_dataset

    dataset = load_dataset("sciq", split="train")

    # Filter the dataset to only include questions with a support
    dataset = dataset.filter(lambda x: x["support"] != "")

    print("Number of questions with support: ", len(dataset))

    # %% [markdown]
    # ### Data loading
    #
    # We load the dataset into a local persistent instance of Chroma, into a collection called `sciq`. We use Chroma's [default embedding function](https://docs.trychroma.com/embeddings#default-all-minilm-l6-v2), all-MiniLM-L6-v2 from [sentence tranformers](https://www.sbert.net/).

    # %%
    import chromadb
    from chromadb.config import Settings

    chroma_client = chromadb.PersistentClient(path="./chroma)")

    collection = chroma_client.get_or_create_collection(name="sciq")

    # %% [markdown]
    # Load the data into Chroma and persist, if it hasn't already been loaded and previously.

    # %%
    # Load the data and persist
    collection.delete()

    from tqdm.notebook import tqdm

    batch_size = 1000
    for i in tqdm(range(0, len(dataset), batch_size)):
        collection.add(
            ids=[str(i) for i in range(i, min(i + batch_size, len(dataset)))],
            documents=dataset["support"][i : i + batch_size],
            metadatas=[{"type": "support"} for _ in range(i, min(i + batch_size, len(dataset)))],
        )

    # %% [markdown]
    # ## Computing a distribution over distances (pseudo density function)
    #
    # We would like to understand the distribution of distances between points in the dataset.
    #
    # To do so, we:
    #
    # 1. Get the computed embeddings of each supporting sentence in the dataset.
    # 2. Use Chroma to efficiently find the distance to each sentence's nearest neighbor.
    # 3. Compute a cumulative density function over distances.
    #
    # Subsequently we can use this cumulative density function to estimate query relevance, by finding the percentile of a given result's distance from the query according to the CDF.
    # A lower percentile means that

    # %%
    # Get the embeddings for the support documents from the collection
    support_embeddings = collection.get(include=["embeddings"])["embeddings"]

    # %% [markdown]
    # We query the collection using the embeddings for each element, returning the distances. Note that we query for two results, since the first (nearest) result will be the element we're querying with.

    # %%
    dists = collection.query(query_embeddings=support_embeddings, n_results=2, include=["distances"])


    # %%
    # Flatten the distances list, excluding the first element (which is an element's distance to itself)
    flat_dists = [item for sublist in dists["distances"] for item in sublist[1:]]

    # %% [markdown]
    # There are some details to note here. Because we query with each element, when two elements are each other's nearest neighbors, the same distance will appear in the result twice. This isn't necessarily a problem if we're computing a cumulative density, as the doubling is taken into account when we normalize to get a cumulative distribution function.
    #
    # However, it is not always the case that the nearest neighbor of some element $a$, will have $a$ as its own nearest neighbor. This could be taken into account by appropriately filtering pairwise matches using the element IDs, but for simplicity we ignore it here.
    # %% [markdown]
    # ### Visualization
    #
    # It can be helpful to visualize the embeddings to get a sense of how they might be distributed and see if there is any obvious structure. We use the [UMAP library](https://umap-learn.readthedocs.io/en/latest/plotting.html) to fit a 2D mainfold to the high-dimensional embedding data, and visualize it.
    # A brighter color indicates a shorter distance to the nearest neighbor.

    # %%
    from umap.umap_ import UMAP
    import umap.plot as umap_plot
    import numpy as np

    mapper = UMAP().fit(support_embeddings)
    umap_plot.points(mapper, values=np.array(flat_dists), show_legend=False, theme="inferno")

    # %% [markdown]
    # ### Computing the density function over distances
    #
    # Using the returned distances, we compute the density function using `numpy`.

    # %%
    # Compute a density function over the distances
    import numpy as np

    hist, bin_edges = np.histogram(flat_dists, bins=100, density=True)
    cumulative_density = np.cumsum(hist) / np.sum(hist)


    # %%
    # Plot the density function
    import matplotlib.pyplot as plt

    plt.plot(bin_edges[1:], hist, label="Density")
    plt.plot(bin_edges[1:], cumulative_density, label="Cumulative Density")
    plt.legend(loc="upper right")
    plt.xlabel("Distance")
    plt.show()

    # %% [markdown]
    # ### Computing relevance using the density function
    #
    # We use the percentile a given query falls into with respect to the overall distribution of distances between elements of the dataset, to estimate its relevance. Intuitively, results which are less relevant to the query, should be in higher percentiles than those which are more relevant.
    #
    # By using the distribution of distances in this way, we eliminate the need to tune an explicit distance threshold, and can instead reason in terms of likelihoods. We could either apply a threshold to the percentile-based relevance directly, or else feed this information into a re-ranking model, or take a sampling approach.


    # %%
    def compute_percentile(dist):
        index = np.searchsorted(bin_edges[1:], dist, side="right")
        return cumulative_density[index - 1]


    # %% [markdown]
    # ## Evaluation
    #
    # We evaluate the percentile based relevance score using the SciQ dataset.
    #
    # 1. We query the collection of supporting sentences using the questions from the dataset, returning the 10 nearest results, along with their distances.
    # 2. We check the results for whether the supporting sentence is present or absent. If it's present in the results, we record the percentile that the support falls into, otherwise we record the percentile of the nearest result.

    # %%
    question_results = collection.query(query_texts=dataset["question"], n_results=10, include=["documents", "distances"])


    # %%
    support_percentiles = []
    missing_support_percentiles = []
    for i, q in enumerate(dataset["question"]):
        support = dataset["support"][i]
        if support in question_results["documents"][i]:
            support_index = question_results["documents"][i].index(support)
            percentile = compute_percentile(question_results["distances"][i][support_index])
            support_percentiles.append(percentile)
        else:
            missing_support_percentiles.append(compute_percentile(question_results["distances"][i][0]))

    # %% [markdown]
    # ### Visualization
    #
    # We plot histograms of the percentiles for the cases where the support was found, and the case where it wasn't. A lower percentile is more relevant.

    # %%
    # Plot normalized histograms of the percentiles
    plt.hist(support_percentiles, bins=20, density=True, alpha=0.5, label="Support")
    plt.hist(missing_support_percentiles, bins=20, density=True, alpha=0.5, label="No support")
    plt.legend(loc="upper right")
    plt.show()

    # %% [markdown]
    # ### Preliminary results
    #
    # While we don't observe a clear separation of the two classes, we do note that in general, supports tend to be in lower percentiles, and hence more relevant, than results which aren't the support.
    #
    # One possible confounding factor is that in some cases, the result does contain the answer to the query question, but is not itself the support for that question.

    # %%
    for i, q in enumerate(dataset["question"][:20]):
        support = dataset["support"][i]
        top_result = question_results["documents"][i][0]

        if support != top_result:
            print(f"Question: {q} \nSupport: {support} \nTop result: {top_result}\n")

    # %% [markdown]
    # ### Conclusion
    #
    # This notebook presents one possible approach to computing a relevance score for embeddings-based retreival, based on the distribution of distances between embeddings in the dataset. We have done some initial evaluation, but there is a lot left to do.
    #
    # Some things to try include:
    # - Construct the distance distribution on the basis of the query-support pairs, rather than between nearest neighbor supports.
    # - Additional evaluations comparing different embedding models for the same dataset, as well as datasets with less redundancy.
    # - Using the distance distribution to deduplicate data, by finding low-percentile outliers. One idea is to use an LLM in the loop to create summaries of document pairs, creating a single point from several which are near one another.
    # - Using relevance as a signal for automatically fine-tuning embedding space. One approach may be to learn an affine transform based on question/answer pairs, to increase the relevance of the correct points relative to others.
    #
    # We welcome contributions and ideas!

if __name__ == "__main__":
    main()