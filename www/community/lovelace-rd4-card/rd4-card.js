customElements.whenDefined('card-tools').then(() => {
class rd4 extends cardTools.LitElement {

  setConfig(config) {
    if(!config || !config.card)
      throw new Error("Invalid configuration");

    this._config = config;
    this.data = {};

    this.entities = this.get_entities() || [];
    this.card = cardTools.createCard(Object.assign({entities: this.entities}, config.card));
  }


  match(pattern, str){
    if (typeof(str) === "string" && typeof(pattern) === "string") {
      if((pattern.startsWith('/') && pattern.endsWith('/')) || pattern.indexOf('*') !== -1) {
        if(pattern[0] !== '/') {
          pattern = pattern.replace(/\./g, '\.');
          pattern = pattern.replace(/\*/g, '.*');
          pattern = `/^${pattern}$/`;
        }
        var regex = new RegExp(pattern.substr(1).slice(0,-1));
        return regex.test(str);
      }
    }
    if(typeof(pattern) === "string") {
      if(pattern.indexOf(":") !== -1 && typeof(str) === "object") {
        while(pattern.indexOf(":") !== -1)
        {
          str = str[pattern.split(":")[0]];
          pattern = pattern.substr(pattern.indexOf(":")+1, pattern.length);
        }
      }
      if(pattern.startsWith("<=")) return parseFloat(str) <= parseFloat(pattern.substr(2));
      if(pattern.startsWith(">=")) return parseFloat(str) >= parseFloat(pattern.substr(2));
      if(pattern.startsWith("<")) return parseFloat(str) < parseFloat(pattern.substr(1));
      if(pattern.startsWith(">")) return parseFloat(str) > parseFloat(pattern.substr(1));
      if(pattern.startsWith("!")) return parseFloat(str) != parseFloat(pattern.substr(1));
      if(pattern.startsWith("=")) return parseFloat(str) == parseFloat(pattern.substr(1));
    }
    return str === pattern;
  }

  match_filter(hass, entities, filter) {
    let retval = [];
    let count = -1;

    Object.keys(filter).forEach((filterKey) => {
      const key = filterKey.split(" ")[0];
      const value = filter[filterKey];
      retval = hass.states[value].attributes.entity_id;
    });
    return retval;
  }

  get_entities()
  {
    let entities = [];
    if(this._config.entities)
      this._config.entities.forEach((e) => entities.push(e));

    if(this._hass && this._config.filter) {

      if(this._config.filter.include){
        this._config.filter.include.forEach((f) => {
          entities = this.match_filter(this._hass, Object.keys(this._hass.states), f);
        });
      }
    }
    return entities;
  }

  createRenderRoot() {
    return this;
  }
  render() {
    if(this.entities.length === 0 && this._config.show_empty === false)
      return cardTools.LitHtml``;
    return cardTools.LitHtml`
      <div id="root">${this.card}</div>
    `;
  }

  async get_data(hass) {
    try {
    this.data.areas = await hass.callWS({type: "config/area_registry/list"});
    this.data.devices = await hass.callWS({type: "config/device_registry/list"});
    this.data.entities = await hass.callWS({type: "config/entity_registry/list"});
    } catch (err) {
    }
  }

  _compare_arrays(a,b) {
    if(a === b) return true;
    if(a == null || b == null) return false;
    if(a.length != b.length) return false;
    for(var i = 0; i < a.length; i++) {
      if(a[i] !== b[i]) {
        return false;
      }
    }
    return true;
  }

  set hass(hass) {
    this._hass = hass;
    this.get_data(hass).then(() => {
      if(this.card)
      {
        this.card.hass = this._hass;
      }

      const oldEntities = this.entities.map((e) => e.entity);
      this.entities = this.get_entities() || [];
      const newEntities = this.entities.map((e) => e.entity);

      if(!this._compare_arrays(oldEntities, newEntities)) {
        this.card.setConfig(Object.assign({entities: this.entities}, this._config.card));
        this.requestUpdate();
      }
    });
  }

}

customElements.define('rd4-card', rd4);
});

window.setTimeout(() => {
  if(customElements.get('card-tools')) return;
  customElements.define('rd4-card', class extends HTMLElement{
    setConfig() { throw new Error("Can't find card-tools. See https://github.com/thomasloven/lovelace-card-tools");}
  });
}, 2000);
