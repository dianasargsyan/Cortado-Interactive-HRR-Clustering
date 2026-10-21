# Contribution Guidelines

Internal Notes (remove or move to different location before publication)

## Sizing images / GIFs in the markdown:
* Size of images and GIFs can be specified the following way:
  * `![medium](screenshots%2Fvariant_handling%2Fvariant_clustering%2Fclustering_dialog.png)`
  * The `medium` above specifies the width of the image/GIF used.
  * Possible other sizes can be `xsmall`, `small`, `medium`, `large`, `xlarge`, `xxlarge`

## Creating Screenshots

Screenshots can be captured consistently by using the fixed cortado window of electron.

### Screenshot without border

![medium](screenshots%2Fvariant_handling%2Fvariant_clustering%2Fclustering_dialog.png)

### Screenshot with border

|![medium](screenshots%2Fvariant_handling%2Fvariant_clustering%2Fclustered_variant_explorer.png)|
-

### Producing GIFs

* Use https://www.screentogif.com/screenshots for creating GIFs similar to the ones below.
* Any part of the screen can be put into the frame that records the GIF.
* There's also a convenient way to post-process and edit the recorded GIFs.
* It should also be made sure to crop out the extra cursor movements at the start or end of the recordings.

|![large](screenshots%2Fprocess_discovery%2Fshift_pt_node.gif)|
-

|![large](screenshots%2Fprocess_discovery%2Fdiscover_initial_model.gif)|
-

### Drawing boxes on screenshots:

  * Drawing numbered boxes on images to refer to sections:
    * Box: Rectangle with 3px border. 
    * Number Text: Calibri, size: 26pt, Bold. 
    * Color Palette for box border and text:
      * Red: #C7171E
      * Green: #22B14C 
      * Purple: #C659C7
      * Blue: #00A2E8
      * Yellow/Gold: #FFC90E
    * See example below which was produced using **paint** in **windows**:

|![box_example.png](screenshots%2Fbox_example.png)|
-

&nbsp;

## Referring to buttons / icons:
  * Examples:
    * Use (<i class="bi bi-diagram-2-fill btn-icon">discover initial model</i>) button to discover an initial model.
    * Click `Files` &rarr; <i class="bi bi-file-earmark-arrow-up btn-icon"></i>`Import process tree (.ptml)` to import an existing process tree from a file.
* Use `code blocks` for referring to something in the UI like a button, an item in the menu or any displayed label in Cortado.
