export class BPMN_Constant {
  public static EVENT_HEIGHT = 40;
  public static EVENT_WIDTH = 120;
  public static START_END_RADIUS = 20;

  public static LINE_COLOR = 'black';

  public static BASE_HEIGHT_WIDTH = 30;
  public static STROKE_WIDTH = 1;
  public static STROKE_COLOR = 'gray';
  public static ARROW_LENGTH = 10;
  public static ARROW_LENGTH_WITHOUT_WINGS = 0.75 * this.ARROW_LENGTH;
  public static CORNER_RADIUS = '3';
  public static INVISIBLE_FONT_SIZE = '2em';
  public static OPERATOR_FONT_SIZE = '1.5em';
  public static VISIBLE_FONT_SIZE = '12px';

  // ensure with maximum that arrows don't get flipped
  public static HORIZONTALSPACING = Math.max(15, this.ARROW_LENGTH);
  public static VERTICALSPACING = Math.max(
    15,
    this.ARROW_LENGTH - (this.EVENT_HEIGHT / 2 - this.STROKE_WIDTH)
  );

  public static OPERATOR_NODE_WIDTH =
    this.BASE_HEIGHT_WIDTH + this.STROKE_WIDTH;
  public static OPERATOR_CENTER = this.OPERATOR_NODE_WIDTH / 2;
  public static OPERATOR_DIAGONAL_LENGTH =
    Math.sqrt(2 * Math.pow(this.OPERATOR_NODE_WIDTH, 2)) / 2;

  public static OPERATOR_COLOR = '#404040';
  public static VISIBLE_ACTIVITIY_DEFAULT_COLOR = '#8f8f8f';
  public static INVISIBLE_ACTIVITIY_DEFAULT_COLOR = '#181818';

  public static PADDING = 5;
  public static MAX_ZOOM = 3;
  public static MIN_ZOOM = 0.1;
  public static DEFAULT_ZOOM = 1;
}
