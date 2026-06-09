import { LightningElement, api } from 'lwc';

export default class __COMPONENT_NAME__ extends LightningElement {
  @api quoteState;
  @api pageState;
  @api metricState;

  showMessage(message, theme = 'success') {
    this.dispatchEvent(new CustomEvent('toastMessageDisplay', {
      detail: { message, theme, timeout: 5000 }
    }));
  }
}
