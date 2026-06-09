import { LightningElement, api } from 'lwc';

export default class __COMPONENT_NAME__ extends LightningElement {
  @api quoteState;
  @api metricState;
  @api pageState;

  @api
  beforeSave() {
    return true;
  }

  @api
  beforeSubmit() {
    return true;
  }

  @api
  beforeRulesExecution() {
    return true;
  }

  @api
  afterRulesExecution() {}
}
