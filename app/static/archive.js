const readerStorageKey = "daybreak.reader.v1";

let readerId = localStorage.getItem(readerStorageKey);

if (!readerId) {
  readerId = crypto.randomUUID();
  localStorage.setItem(readerStorageKey, readerId);
}

window.daybreakReaderId = readerId;

function showSavedEdition(paper) {
  stories.replaceChildren();

  paper.articles.forEach(story => {
    stories.appendChild(createStory(story));
  });

  const created = new Date(paper.created_at).toLocaleString();

  editionInfo.textContent =
    `${paper.count} stories · ` +
    `About ${paper.estimated_reading_minutes} min · ` +
    `Created ${created}`;

  warningsElement.textContent =
    (paper.warnings || []).join(" ");

  form.hidden = true;
  edition.hidden = false;

  window.daybreakEditionId = paper.edition_id;

  statusElement.textContent =
    "Opened a saved edition. Its stories have not changed.";

  edition.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

async function loadArchive() {
  const archiveList = document.getElementById("archive-list");
  const archiveStatus = document.getElementById("archive-status");

  archiveStatus.textContent = "Loading saved papers...";

  try {
    const response = await fetch("/api/editions", {
      headers: {
        "X-Reader-ID": window.daybreakReaderId
      }
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();

    archiveList.replaceChildren();

    if (!data.editions.length) {
      archiveStatus.textContent =
        "No saved papers yet. Create your first paper above.";
      return;
    }

    archiveStatus.textContent =
      `${data.editions.length} saved editions`;

    data.editions.forEach(item => {
      const button = document.createElement("button");

      const created = new Date(item.created_at).toLocaleString();

      button.type = "button";
      button.textContent =
        `${created} · ${item.count} stories · ` +
        item.topics.join(", ");

      button.style.display = "block";
      button.style.margin = "10px 0";
      button.style.textAlign = "left";
      button.style.lineHeight = "1.5";

      button.addEventListener("click", async () => {
        button.disabled = true;
        archiveStatus.textContent = "Opening saved paper...";

        try {
          const response = await fetch(
            `/api/editions/${item.edition_id}`,
            {
              headers: {
                "X-Reader-ID": window.daybreakReaderId
              }
            }
          );

          if (!response.ok) {
            throw new Error("Could not open this edition.");
          }

          const paper = await response.json();

          showSavedEdition(paper);
          archiveStatus.textContent = "Saved paper opened.";
        } catch (error) {
          archiveStatus.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      });

      archiveList.appendChild(button);
    });
  } catch (error) {
    archiveStatus.textContent =
      `Could not load archive: ${error.message}`;
  }
}

window.loadDaybreakArchive = loadArchive;

loadArchive();