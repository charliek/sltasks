"""GraphQL query templates for GitHub Projects API."""

# Query to get a user's project by number
GET_USER_PROJECT = """
query GetUserProject($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 20) {
        nodes {
          ... on ProjectV2Field {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}
"""

# Query to get an organization's project by number
GET_ORG_PROJECT = """
query GetOrgProject($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 20) {
        nodes {
          ... on ProjectV2Field {
            id
            name
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
    }
  }
}
"""

# Query to get project items (issues and PRs)
GET_PROJECT_ITEMS = """
query GetProjectItems($projectId: ID!, $cursor: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field {
                  ... on ProjectV2SingleSelectField {
                    name
                  }
                }
                name
                optionId
              }
            }
          }
          content {
            ... on Issue {
              id
              number
              title
              body
              state
              labels(first: 20) {
                nodes {
                  name
                }
              }
              createdAt
              updatedAt
              repository {
                nameWithOwner
              }
            }
            ... on PullRequest {
              id
              number
              title
              body
              state
              isDraft
              labels(first: 20) {
                nodes {
                  name
                }
              }
              createdAt
              updatedAt
              repository {
                nameWithOwner
              }
            }
            ... on DraftIssue {
              title
              body
              createdAt
              updatedAt
            }
          }
        }
      }
    }
  }
}
"""

# Mutation to update a project item's field value (e.g., Status)
UPDATE_ITEM_FIELD = """
mutation UpdateItemField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(
    input: {
      projectId: $projectId
      itemId: $itemId
      fieldId: $fieldId
      value: { singleSelectOptionId: $optionId }
    }
  ) {
    projectV2Item {
      id
    }
  }
}
"""

# Mutation to update item position within a project view
UPDATE_ITEM_POSITION = """
mutation UpdateItemPosition($projectId: ID!, $itemId: ID!, $afterId: ID) {
  updateProjectV2ItemPosition(
    input: {
      projectId: $projectId
      itemId: $itemId
      afterId: $afterId
    }
  ) {
    items(first: 1) {
      nodes {
        id
      }
    }
  }
}
"""

# Mutation to create a new issue
CREATE_ISSUE = """
mutation CreateIssue($repositoryId: ID!, $title: String!, $body: String) {
  createIssue(
    input: {
      repositoryId: $repositoryId
      title: $title
      body: $body
    }
  ) {
    issue {
      id
      number
      title
      body
      createdAt
      updatedAt
      repository {
        nameWithOwner
      }
    }
  }
}
"""

# Mutation to update an existing issue
UPDATE_ISSUE = """
mutation UpdateIssue($issueId: ID!, $title: String, $body: String) {
  updateIssue(
    input: {
      id: $issueId
      title: $title
      body: $body
    }
  ) {
    issue {
      id
      number
      title
      body
      updatedAt
    }
  }
}
"""

# Mutation to close an issue
CLOSE_ISSUE = """
mutation CloseIssue($issueId: ID!) {
  closeIssue(input: { issueId: $issueId }) {
    issue {
      id
      state
    }
  }
}
"""

# Mutation to reopen an issue
REOPEN_ISSUE = """
mutation ReopenIssue($issueId: ID!) {
  reopenIssue(input: { issueId: $issueId }) {
    issue {
      id
      state
    }
  }
}
"""

# Mutation to add an issue/PR to a project
ADD_ITEM_TO_PROJECT = """
mutation AddItemToProject($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(
    input: {
      projectId: $projectId
      contentId: $contentId
    }
  ) {
    item {
      id
    }
  }
}
"""

# Query to get repository ID by owner/name
GET_REPOSITORY = """
query GetRepository($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    nameWithOwner
  }
}
"""

# Mutation to add labels to an issue
ADD_LABELS = """
mutation AddLabels($labelableId: ID!, $labelIds: [ID!]!) {
  addLabelsToLabelable(
    input: {
      labelableId: $labelableId
      labelIds: $labelIds
    }
  ) {
    labelable {
      ... on Issue {
        id
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
}
"""

# Mutation to remove labels from an issue
REMOVE_LABELS = """
mutation RemoveLabels($labelableId: ID!, $labelIds: [ID!]!) {
  removeLabelsFromLabelable(
    input: {
      labelableId: $labelableId
      labelIds: $labelIds
    }
  ) {
    labelable {
      ... on Issue {
        id
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
}
"""

# Query to get labels from a repository
GET_REPOSITORY_LABELS = """
query GetRepositoryLabels($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    labels(first: 100) {
      nodes {
        id
        name
      }
    }
  }
}
"""
